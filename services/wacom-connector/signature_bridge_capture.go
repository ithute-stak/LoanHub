package main

// Staging-only offline signature adapter. Unlike the diagnostic summary path,
// this command intentionally emits captured point coordinates to stdout for
// immediate consumption by the encrypted local Signature Bridge. It never
// exposes pen data over HTTP, and is not a contract-signing authorization.
import (
    "encoding/json"
    "errors"
    "fmt"
    "os"
    "path/filepath"
    "strings"
    "syscall"
    "time"
)

type bridgePenPoint struct {
    X float64 `json:"x"`
    Y float64 `json:"y"`
    Pressure float64 `json:"pressure"`
    Tick int `json:"t"`
}
type bridgePenEnvelope struct {
    Format string `json:"format"`
    Strokes [][]bridgePenPoint `json:"strokes"`
}
type bridgeSDKConfig struct {
    Query string `json:"sdk_query"`
    PenSample string `json:"sdk_pen_sample"`
}

func loadBridgeSDKConfig() (bridgeSDKConfig, error) {
    var cfg bridgeSDKConfig
    if os.Getenv("LOANHUB_SIGNATURE_BRIDGE_MODE") != "staging" {
        return cfg, errors.New("offline pen adapter requires staging mode")
    }
    home, err := os.UserHomeDir()
    if err != nil { return cfg, errors.New("home directory unavailable") }
    location := filepath.Join(home, ".config", "loanhub-signature-bridge", "wacom-sdk.json")
    info, err := os.Lstat(location)
    if err != nil || !info.Mode().IsRegular() || info.Mode().Perm()&0077 != 0 {
        return cfg, errors.New("private SDK configuration unavailable")
    }
    owner, ok := info.Sys().(*syscall.Stat_t)
    if !ok || owner.Uid != uint32(os.Getuid()) {
        return cfg, errors.New("SDK configuration must belong to the desktop operator")
    }
    data, err := os.ReadFile(location)
    if err != nil || len(data) > 4096 {
        return cfg, errors.New("SDK configuration unavailable")
    }
    if err := json.Unmarshal(data, &cfg); err != nil {
        return cfg, errors.New("invalid SDK configuration")
    }
    for _, path := range []string{cfg.Query, cfg.PenSample} {
        if !filepath.IsAbs(path) || !safeSamplePath.MatchString(path) {
            return cfg, errors.New("SDK sample path must be absolute and safe")
        }
        st, err := os.Lstat(path)
        if err != nil || !st.Mode().IsRegular() || st.Mode().Perm()&0111 == 0 ||
           st.Mode().Perm()&0022 != 0 {
            return cfg, errors.New("SDK binary unavailable or writable by untrusted users")
        }
        binaryOwner, ok := st.Sys().(*syscall.Stat_t)
        if !ok || (binaryOwner.Uid != 0 && binaryOwner.Uid != uint32(os.Getuid())) {
            return cfg, errors.New("SDK binary ownership is not trusted")
        }
    }
    return cfg, nil
}

// Calibration dimensions come from the vendor SDK query executable, never from
// untrusted pen output. The output is only normalized stroke coordinates.
func captureBridgeStrokes(cfg bridgeSDKConfig) (bridgePenEnvelope, error) {
    failed := bridgePenEnvelope{}
    calibration, err := queryLocalSDKCalibration(cfg.Query)
    if err != nil { return failed, errors.New("Wacom calibration unavailable") }
    if calibration.MaxX <= 0 || calibration.MaxY <= 0 || calibration.MaxPressure <= 0 {
        return failed, errors.New("invalid Wacom calibration dimensions")
    }
    envelope := bridgePenEnvelope{Format:"loanhub-pen-strokes-v1"}
    var stroke []bridgePenPoint
    lastTime := -1
    callback := func(p penSample) error {
        if p.Ready != 1 || p.Switch != 1 || p.Pressure == 0 {
            if len(stroke) >= 2 {
                envelope.Strokes = append(envelope.Strokes, stroke)
                if len(envelope.Strokes) > 128 { return errors.New("too many strokes") }
            }
            stroke = nil
            lastTime = -1
            return nil
        }
        if p.X < 0 || p.Y < 0 || p.Pressure < 0 ||
           p.X > calibration.MaxX || p.Y > calibration.MaxY ||
           p.Pressure > calibration.MaxPressure {
            return errors.New("out-of-bounds Wacom pen report")
        }
        tick := p.Time
        if tick <= lastTime { tick = lastTime + 1 }
        if tick > 300000 { return errors.New("pen report time exceeded limit") }
        lastTime = tick
        stroke = append(stroke, bridgePenPoint{
            X: float64(p.X)/float64(calibration.MaxX),
            Y: float64(p.Y)/float64(calibration.MaxY),
            Pressure: float64(p.Pressure)/float64(calibration.MaxPressure),
            Tick: tick,
        })
        if len(stroke) > 8192 { return errors.New("pen point budget exceeded") }
        return nil
    }
    _, err = testWacomSampleWithHandler(cfg.PenSample, 25*time.Second, callback)
    if err != nil { return failed, errors.New("Wacom pen stream capture failed") }
    if len(stroke) >= 2 { envelope.Strokes = append(envelope.Strokes, stroke) }
    if len(envelope.Strokes) == 0 || len(envelope.Strokes) > 128 {
        return failed, errors.New("no valid Wacom pen strokes")
    }
    total := 0
    for _, s := range envelope.Strokes { total += len(s) }
    if total > 8192 { return failed, errors.New("pen point budget exceeded") }
    encoded, err := json.Marshal(envelope)
    if err != nil || len(encoded) > 128000 {
        return failed, errors.New("Wacom capture exceeds the local envelope limit")
    }
    return envelope, nil
}

func runBridgeCaptureCLI() error {
    cfg, err := loadBridgeSDKConfig()
    if err != nil { return err }
    if !isOperatorTerminalStdin() {
        return fmt.Errorf("operator terminal required for interactive STU capture")
    }
    fmt.Fprintln(os.Stderr, strings.TrimSpace("Wacom staging capture: use only synthetic/test signatures"))
    capture, err := captureBridgeStrokes(cfg)
    if err != nil { return err }
    return json.NewEncoder(os.Stdout).Encode(capture)
}
