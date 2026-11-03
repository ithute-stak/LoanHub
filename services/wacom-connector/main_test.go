package main

import (
    "encoding/json"
    "net/http"
    "net/http/httptest"
    "testing"
)

func request(t *testing.T, method, path, host, origin string) *httptest.ResponseRecorder {
    t.Helper()
    req := httptest.NewRequest(method, "http://127.0.0.1:8765"+path, nil)
    req.Host = host
    if origin != "" { req.Header.Set("Origin", origin) }
    recorder := httptest.NewRecorder()
    handler(recorder, req)
    return recorder
}

func TestStatusFailClosed(t *testing.T) {
    w := request(t, "GET", "/v1/device/status", "127.0.0.1:8765", "https://loanhub.co.ls")
    if w.Code != http.StatusOK { t.Fatalf("status %d", w.Code) }
    if w.Header().Get("Access-Control-Allow-Origin") != "https://loanhub.co.ls" { t.Fatal("Missing pinned CORS origin") }
    if w.Header().Get("Cache-Control") != "no-store" { t.Fatal("Diagnostics must not be cached") }
    var body deviceStatus
    if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil { t.Fatal(err) }
    if body.Protocol != protocol || body.Connected { t.Fatalf("Device must remain unavailable: %+v", body) }
}

func TestRejectOtherOriginsAndHosts(t *testing.T) {
    for _, tt := range []struct{host, origin string}{
        {"localhost:8765", "https://loanhub.co.ls"},
        {"evil.example:8765", "https://loanhub.co.ls"},
        {"127.0.0.1:8765", "https://evil.example"},
        {"127.0.0.1:8765", "http://loanhub.co.ls"},
        {"127.0.0.1:8765", "https://loanhub.co.ls.evil.example"},
        {"127.0.0.1:8765", "https://loanhub.co.ls:443"},
    } {
        w := request(t, "GET", "/v1/device/status", tt.host, tt.origin)
        if w.Code != http.StatusForbidden || w.Header().Get("Access-Control-Allow-Origin") != "" {
            t.Errorf("host=%q origin=%q: status=%d, CORS=%q", tt.host, tt.origin, w.Code, w.Header().Get("Access-Control-Allow-Origin"))
        }
    }
}

func TestNoSigningOrCaptureRoute(t *testing.T) {
    for _, path := range []string{"/v1/sign", "/v1/capture", "/v1/device/claim"} {
        w := request(t, "POST", path, "127.0.0.1:8765", "https://loanhub.co.ls")
        if w.Code != http.StatusNotFound { t.Errorf("%s: %d", path, w.Code) }
    }
    w := request(t, "POST", "/v1/device/status", "127.0.0.1:8765", "")
    if w.Code != http.StatusMethodNotAllowed { t.Fatalf("Method should be rejected: %d", w.Code) }
}
