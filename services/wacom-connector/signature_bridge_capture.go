package main

// Staging-only offline signature adapter. Unlike the diagnostic summary path,
// this command intentionally emits captured point coordinates to stdout for
// immediate consumption by the encrypted local Signature Bridge. It never
// exposes pen data over HTTP, and is not a contract-signing authorization.
import (
    "encoding/json"
    "context"
    "errors"
    "fmt"
    "os"
    "os/exec"
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

// bridgeStrokeCollector is deliberately pure: SDK parsing and stroke assembly
// can be tested without any tablet, terminal, or customer handwriting.
type bridgeStrokeCollector struct {
    maxX, maxY, maxPressure int
    strokes [][]bridgePenPoint
    current []bridgePenPoint
    previousTime int
    total int
}

func newBridgeStrokeCollector(x, y, pressure int) (*bridgeStrokeCollector, error) {
    if x <= 0 || y <= 0 || pressure <= 0 {
        return nil, errors.New("invalid tablet calibration")
    }
    return &bridgeStrokeCollector{maxX:x, maxY:y, maxPressure:pressure, previousTime:-1}, nil
}

func (c *bridgeStrokeCollector) finishStroke() error {
    if len(c.current) >= 2 {
        c.strokes = append(c.strokes, c.current)
        if len(c.strokes) > 128 { return errors.New("too many pen strokes") }
    }
    c.current = nil
    c.previousTime = -1
    return nil
}

func (c *bridgeStrokeCollector) Add(p penSample) error {
    if p.Ready != 1 || p.Switch != 1 || p.Pressure == 0 {
        return c.finishStroke()
    }
    if p.X < 0 || p.Y < 0 || p.Pressure < 0 ||
       p.X > c.maxX || p.Y > c.maxY || p.Pressure > c.maxPressure {
        return errors.New("out-of-bounds Wacom pen report")
    }
    if c.total >= 8192 { return errors.New("pen point budget exceeded") }
    tick := p.Time
    if tick <= c.previousTime { tick = c.previousTime+1 }
    if tick > 300000 { return errors.New("pen report time exceeded limit") }
    c.previousTime = tick
    c.current = append(c.current, bridgePenPoint{
        X:float64(p.X)/float64(c.maxX),
        Y:float64(p.Y)/float64(c.maxY),
        Pressure:float64(p.Pressure)/float64(c.maxPressure),
        Tick:tick,
    })
    c.total++
    return nil
}

func (c *bridgeStrokeCollector) Envelope() (bridgePenEnvelope, error) {
    failed := bridgePenEnvelope{}
    if err := c.finishStroke(); err != nil { return failed, err }
    if len(c.strokes) == 0 || len(c.strokes) > 128 {
        return failed, errors.New("no valid Wacom pen strokes")
    }
    envelope := bridgePenEnvelope{Format:"loanhub-pen-strokes-v1", Strokes:c.strokes}
    encoded,err := json.Marshal(envelope)
    if err != nil || len(encoded) > 128000 {
        return failed, errors.New("Wacom capture exceeds the local envelope limit")
    }
    return envelope, nil
}

// Calibration dimensions come from the official SDK query executable, not
// from a client, a browser or the pen report stream itself.
func captureBridgeStrokes(cfg bridgeSDKConfig, duration time.Duration) (bridgePenEnvelope, error) {
    failed := bridgePenEnvelope{}
    calibration, err := queryLocalSDKCalibration(cfg.Query)
    if err != nil { return failed, errors.New("Wacom calibration unavailable") }
    collector, err := newBridgeStrokeCollector(
        calibration.MaxX, calibration.MaxY, calibration.MaxPressure,
    )
    if err != nil { return failed, err }
    _, err = testWacomSampleWithHandler(cfg.PenSample, duration, collector.Add)
    if err != nil { return failed, errors.New("Wacom pen stream capture failed") }
    return collector.Envelope()
}

// This dry-run validates local prerequisites without opening the STU tablet,
// starting a Wacom SDK sample, or producing/storing handwriting.
func preflightBridgeCaptureCLI() error {
    cfg, err := loadBridgeSDKConfig()
    if err != nil { return err }
    if _, err := exec.LookPath("script"); err != nil {
        return errors.New("util-linux script is required for Wacom PTY capture")
    }
    if !isOperatorTerminalStdin() {
        return errors.New("interactive operator terminal required for real capture")
    }
    if cfg.Query == cfg.PenSample {
        return errors.New("calibration and pen sample executables must be distinct")
    }
    // Deliberately no SDK invocation or device access during preflight.
    return json.NewEncoder(os.Stdout).Encode(map[string]interface{}{
        "status": "prerequisites_ready",
        "mode": "staging",
        "device_checked": false,
        "capture_performed": false,
        "hardware_verified": false,
        "signing_enabled": false,
    })
}

func runBridgeCaptureCLI(fast bool) error {
    cfg, err := loadBridgeSDKConfig()
    if err != nil { return err }
    if !isOperatorTerminalStdin() {
        return fmt.Errorf("operator terminal required for interactive STU capture")
    }
    fmt.Fprintln(os.Stderr, strings.TrimSpace("Wacom staging capture: use only synthetic/test signatures"))
    duration := 25 * time.Second
    if fast { duration = 10 * time.Second }
    capture, err := captureBridgeStrokes(cfg, duration)
    if err != nil { return err }
    return json.NewEncoder(os.Stdout).Encode(capture)
}

// runBridgePenContactWatchCLI detects only the first actual pen-down report.
// It intentionally discards all coordinates, IDs, and gesture content.
// The SDK itself still needs a real foreground terminal for its PTY.
func runBridgePenContactWatchCLI() error {
    cfg, err := loadBridgeSDKConfig()
    if err != nil { return err }
    if !isOperatorTerminalStdin() {
        return errors.New("interactive terminal required for pen-contact watch")
    }
    ctx, cancel := context.WithCancel(context.Background())
    defer cancel()
    detected := false
    _, err = testWacomSampleWithContext(ctx, cfg.PenSample, 25*time.Second, func(sample penSample) error {
        if sample.Ready == 1 && sample.Switch == 1 && sample.Pressure > 0 {
            detected = true
            cancel()
            return errPenContactDetected
        }
        return nil
    })
    if detected {
        // Exactly one fixed status token; never the raw pen report.
        fmt.Fprintln(os.Stdout, "pen-contact")
        return nil
    }
    if err != nil { return err }
    return nil
}

var errPenContactDetected = errors.New("pen contact detected")
