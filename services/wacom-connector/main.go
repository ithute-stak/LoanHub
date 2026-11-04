// LoanHub Wacom STU workstation connector (diagnostics-only foundation).
// Native Wacom SDK access, signing, evidence transfer and device claiming are NOT implemented.
package main

import (
    "encoding/json"
    "errors"
    "flag"
    "log"
    "net"
    "net/http"
    "net/url"
    "path/filepath"
    "strings"
    "os"
    "time"
)

const listenAddr = "127.0.0.1:8765"
const protocol = "loanhub-wacom-v1"

// Startup-only SDK enumeration. Does not enable SDK capture or tablet access.
var startupSDKDetected bool

type deviceStatus struct {
    Protocol  string `json:"protocol"`
    Connected bool   `json:"connected"`
    Model     string `json:"model,omitempty"`
    USBDetected bool `json:"usb_detected"`
    SDKDetected bool `json:"sdk_detected"`
}

func allowedOrigin(origin string) bool {
    if origin == "" {
        return true // Direct local diagnostic clients have no browser Origin.
    }
    parsed, err := url.Parse(origin)
    if err != nil || parsed.Scheme != "https" || parsed.User != nil ||
        parsed.Host != "loanhub.co.ls" || parsed.RawQuery != "" ||
        parsed.Fragment != "" || parsed.Path != "" {
        return false
    }
    return origin == "https://loanhub.co.ls"
}

func allowedHost(host string) bool {
    return host == "127.0.0.1:8765"
}

// USB identification is diagnostic only: it does not mean SDK access,
// pen capture, borrower consent or signing is available.
func findSTU540(root string) bool {
    entries, err := os.ReadDir(root)
    if err != nil { return false }
    for _, entry := range entries {
        if !entry.IsDir() && entry.Type()&os.ModeSymlink == 0 { continue }
        base := filepath.Join(root, entry.Name())
        vendor, errV := os.ReadFile(filepath.Join(base, "idVendor"))
        product, errP := os.ReadFile(filepath.Join(base, "idProduct"))
        if errV == nil && errP == nil &&
            strings.EqualFold(strings.TrimSpace(string(vendor)), "056a") &&
            strings.EqualFold(strings.TrimSpace(string(product)), "00a8") {
            return true
        }
    }
    return false
}

func handler(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Cache-Control", "no-store")
    w.Header().Set("X-Content-Type-Options", "nosniff")
    if !allowedHost(r.Host) || !allowedOrigin(r.Header.Get("Origin")) {
        http.Error(w, "Forbidden", http.StatusForbidden)
        return
    }
    if origin := r.Header.Get("Origin"); origin != "" {
        w.Header().Set("Access-Control-Allow-Origin", origin)
        w.Header().Set("Vary", "Origin")
    }
    // No capture/consent routes should exist until device attestation and
    // backend-authorized signing sessions have been implemented.
    if r.URL.Path != "/v1/device/status" {
        http.NotFound(w, r)
        return
    }
    if r.Method != http.MethodGet {
        w.Header().Set("Allow", http.MethodGet)
        http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
        return
    }
    w.Header().Set("Content-Type", "application/json")
    detected := findSTU540("/sys/bus/usb/devices")
    status := deviceStatus{Protocol: protocol, Connected: false, USBDetected: detected, SDKDetected: detected && startupSDKDetected}
    if detected { status.Model = "STU-540" }
    _ = json.NewEncoder(w).Encode(status)
}

func serve() error {
    // Explicit TCP loopback binding: never expose status or future SDK APIs on LAN.
    listener, err := net.Listen("tcp4", listenAddr)
    if err != nil {
        return err
    }
    defer listener.Close()
    server := &http.Server{
        Handler:           http.HandlerFunc(handler),
        ReadHeaderTimeout: 3 * time.Second,
        ReadTimeout:       5 * time.Second,
        WriteTimeout:      5 * time.Second,
        IdleTimeout:       10 * time.Second,
        MaxHeaderBytes:    8192,
    }
    err = server.Serve(listener)
    if errors.Is(err, http.ErrServerClosed) {
        return nil
    }
    return err
}

func main() {
    diagnostics := flag.Bool("diagnostics", false, "Start local diagnostic-only status service")
    sdkEnumerator := flag.String("sdk-enumerator", "", "Absolute path to official Wacom SDK getUsbDevices executable")
    penTest := flag.Bool("pen-test", false, "Run bounded local hardware diagnostic (does not sign contracts)")
    calibrationTest := flag.Bool("calibration-test", false, "Read official STU SDK tablet capabilities locally (not signing)")
    calibratedStrokeTest := flag.Bool("calibrated-stroke-test", false, "Validate disposable native strokes against verified SDK calibration (no signing)")
    sdkQuery := flag.String("sdk-query", "", "Absolute path to official Wacom SDK query executable")
    strokeTest := flag.Bool("stroke-test", false, "Assemble test strokes locally in memory (does not sign contracts)")
    sdkPenSample := flag.String("sdk-pen-sample", "", "Absolute path to vendor SDK simpleInterface sample")
    flag.Parse()
    if *calibrationTest {
        if *calibratedStrokeTest || *diagnostics || *penTest || *strokeTest || *sdkEnumerator != "" || *sdkPenSample != "" || *sdkQuery == "" || len(flag.Args()) != 0 {
            log.Println("Use --calibration-test --sdk-query=/absolute/path/to/query")
            os.Exit(2)
        }
        calibration, err := queryLocalSDKCalibration(*sdkQuery)
        if err != nil { log.Printf("Wacom calibration test failed: %v",err); os.Exit(1) }
        log.Printf("Wacom SDK calibration: tabletMaxX=%d tabletMaxY=%d tabletMaxPressure=%d (local diagnostic only; no signing).",calibration.MaxX,calibration.MaxY,calibration.MaxPressure)
        return
    }
    if *calibratedStrokeTest {
        if *diagnostics || *penTest || *strokeTest || *sdkEnumerator != "" || *sdkPenSample == "" || *sdkQuery == "" || len(flag.Args()) != 0 {
            log.Println("Use --calibrated-stroke-test --sdk-query=/absolute/path/to/query --sdk-pen-sample=/absolute/path/to/simpleInterface")
            os.Exit(2)
        }
        log.Println("Local calibrated Wacom test: vendor calibration first, then draw disposable TEST strokes after SDK ready (no signing, no persistence).")
        summary, err := testCalibratedLocalStrokes(*sdkQuery, *sdkPenSample, 25*time.Second)
        if err != nil { log.Printf("Wacom calibrated stroke test failed: %v", err); os.Exit(1) }
        log.Printf("Calibrated local test passed: tabletMaxX=%d tabletMaxY=%d tabletMaxPressure=%d, %d SDK reports, %d contact points, %d strokes, %d valid preview points (nothing saved or uploaded).",
            summary.Calibration.MaxX, summary.Calibration.MaxY, summary.Calibration.MaxPressure,
            summary.PenReports, summary.ContactPoints, summary.Strokes, summary.PreviewPoints)
        return
    }
    if *sdkQuery != "" { log.Println("--sdk-query is only allowed with --calibration-test or --calibrated-stroke-test"); os.Exit(2) }
    if *penTest && *strokeTest {
        log.Println("Choose exactly one of --pen-test or --stroke-test")
        os.Exit(2)
    }
    if *strokeTest {
        if *diagnostics || *sdkEnumerator != "" || *sdkPenSample == "" || len(flag.Args()) != 0 {
            log.Println("Use --stroke-test --sdk-pen-sample=/absolute/path/to/simpleInterface")
            os.Exit(2)
        }
        log.Println("Local stroke test: draw disposable strokes after SDK ready; no handwriting saved.")
        summary, err := testLocalStrokes(*sdkPenSample, 25*time.Second)
        if err != nil { log.Printf("Wacom stroke test failed: %v", err); os.Exit(1) }
        log.Printf("Local stroke test: %d SDK reports, %d contact points, %d strokes (no signing).", summary.PenReports, summary.ContactPoints, summary.Strokes)
        return
    }
    if *penTest {
        if *diagnostics || *sdkEnumerator != "" || *sdkPenSample == "" || len(flag.Args()) != 0 {
            log.Println("Use --pen-test --sdk-pen-sample=/absolute/path/to/simpleInterface")
            os.Exit(2)
        }
        log.Println("Local Wacom pen diagnostic: wait for SDK ready, then draw TEST strokes; 25-second maximum, nothing saved.")
        count, err := testWacomPenSample(*sdkPenSample, 25*time.Second)
        if err != nil { log.Printf("Wacom test failed: %v", err); os.Exit(1) }
        log.Printf("Observed %d vendor SDK pen reports (not a contract signature).", count)
        if count == 0 { os.Exit(1) }
        return
    }
    if !*diagnostics || *sdkPenSample != "" || len(flag.Args()) != 0 {
        log.Println("Native device capture is unavailable. Start with --diagnostics for status-only mode.")
        os.Exit(2)
    }
    if *sdkEnumerator != "" {
        detected, err := probeSDK(*sdkEnumerator)
        if err != nil {
            log.Printf("SDK device enumeration unavailable: %v (capture remains disabled)", err)
        } else {
            startupSDKDetected = detected
            log.Printf("Official SDK enumeration found STU-540: %t", detected)
        }
    }
    log.Printf("LoanHub Wacom diagnostics listening on %s (no hardware signing enabled)", listenAddr)
    if err := serve(); err != nil {
        log.Fatal(err)
    }
}

