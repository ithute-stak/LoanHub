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
    "os"
    "strings"
    "time"
)

const listenAddr = "127.0.0.1:8765"
const protocol = "loanhub-wacom-v1"

type deviceStatus struct {
    Protocol  string `json:"protocol"`
    Connected bool   `json:"connected"`
    Model     string `json:"model,omitempty"`
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
    _ = json.NewEncoder(w).Encode(deviceStatus{Protocol: protocol, Connected: false})
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
    flag.Parse()
    if !*diagnostics || len(flag.Args()) != 0 {
        log.Println("Native device capture is unavailable. Start with --diagnostics for status-only mode.")
        os.Exit(2)
    }
    log.Printf("LoanHub Wacom diagnostics listening on %s (no hardware signing enabled)", listenAddr)
    if err := serve(); err != nil {
        log.Fatal(err)
    }
}

// Avoid accidental future expansion: no env-based bind overrides, no remote
// access, no device serial numbers and no user or contract data in diagnostics.
var _ = strings.TrimSpace
