package main

import (
    "os"
    "encoding/json"
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

func TestBridgeCaptureRejectsSymlinkSDKBinary(t *testing.T) {
    home := t.TempDir()
    t.Setenv("HOME", home)
    t.Setenv("LOANHUB_SIGNATURE_BRIDGE_MODE", "staging")
    folder := filepath.Join(home, ".config", "loanhub-signature-bridge")
    if err := os.MkdirAll(folder, 0700); err != nil { t.Fatal(err) }
    executable := filepath.Join(home, "sdk-test")
    if err := os.WriteFile(executable, []byte("#!/bin/sh\\n"), 0700); err != nil { t.Fatal(err) }
    link := filepath.Join(home, "sdk-link")
    if err := os.Symlink(executable, link); err != nil { t.Fatal(err) }
    data, _ := json.Marshal(bridgeSDKConfig{Query: executable, PenSample: link})
    cfg := filepath.Join(folder, "wacom-sdk.json")
    if err := os.WriteFile(cfg, data, 0600); err != nil { t.Fatal(err) }
    if _, err := loadBridgeSDKConfig(); err == nil {
        t.Fatal("symlinked SDK binaries must fail closed")
    }
}

func TestBridgeCaptureRejectsWritableSDKBinary(t *testing.T) {
    home := t.TempDir()
    t.Setenv("HOME", home)
    t.Setenv("LOANHUB_SIGNATURE_BRIDGE_MODE", "staging")
    folder := filepath.Join(home, ".config", "loanhub-signature-bridge")
    if err := os.MkdirAll(folder, 0700); err != nil { t.Fatal(err) }
    executable := filepath.Join(home, "sdk-test")
    if err := os.WriteFile(executable, []byte("#!/bin/sh\\n"), 0777); err != nil { t.Fatal(err) }
    if err := os.Chmod(executable, 0777); err != nil { t.Fatal(err) }
    data, _ := json.Marshal(bridgeSDKConfig{Query: executable, PenSample: executable})
    if err := os.WriteFile(filepath.Join(folder, "wacom-sdk.json"), data, 0600); err != nil { t.Fatal(err) }
    if _, err := loadBridgeSDKConfig(); err == nil {
        t.Fatal("group/world writable SDK binaries must fail closed")
    }
}

func TestBridgePreflightDoesNotOpenSDKWithoutConfig(t *testing.T) {
    t.Setenv("HOME", t.TempDir())
    t.Setenv("LOANHUB_SIGNATURE_BRIDGE_MODE", "staging")
    if err := preflightBridgeCaptureCLI(); err == nil {
        t.Fatal("preflight must fail closed when official SDK config is absent")
    }
}

func TestBridgePreflightFailsInProduction(t *testing.T) {
    t.Setenv("LOANHUB_SIGNATURE_BRIDGE_MODE", "production")
    if err := preflightBridgeCaptureCLI(); err == nil {
        t.Fatal("production preflight must not authorize capture")
    }
}
