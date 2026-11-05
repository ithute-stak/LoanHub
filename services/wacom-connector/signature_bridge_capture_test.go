package main

import (
    "os"
    "path/filepath"
    "testing"
)

func TestBridgeCaptureConfigFailsClosedWithoutStaging(t *testing.T) {
    t.Setenv("LOANHUB_SIGNATURE_BRIDGE_MODE", "production")
    if _, err := loadBridgeSDKConfig(); err == nil {
        t.Fatal("production must not load offline signature capture")
    }
}

func TestBridgeCaptureConfigFailsClosedWithoutPrivateConfig(t *testing.T) {
    t.Setenv("LOANHUB_SIGNATURE_BRIDGE_MODE", "staging")
    t.Setenv("HOME", t.TempDir())
    if _, err := loadBridgeSDKConfig(); err == nil {
        t.Fatal("missing SDK paths must disable capture")
    }
}

func TestBridgeCaptureConfigRejectsInsecurePermissions(t *testing.T) {
    home := t.TempDir()
    t.Setenv("HOME", home)
    t.Setenv("LOANHUB_SIGNATURE_BRIDGE_MODE", "staging")
    folder := filepath.Join(home, ".config", "loanhub-signature-bridge")
    if err := os.MkdirAll(folder, 0700); err != nil { t.Fatal(err) }
    file := filepath.Join(folder, "wacom-sdk.json")
    if err := os.WriteFile(file, []byte(`{"sdk_query":"/tmp/query","sdk_pen_sample":"/tmp/sample"}`), 0644); err != nil { t.Fatal(err) }
    if _, err := loadBridgeSDKConfig(); err == nil {
        t.Fatal("group-readable SDK configuration must be rejected")
    }
}
