package main

import (
    "os"
    "path/filepath"
    "runtime"
    "testing"
)

func TestSDKEnumerationHonorsExactDeviceID(t *testing.T) {
    if runtime.GOOS == "windows" { t.Skip("POSIX shell test") }
    dir := t.TempDir()
    executable := filepath.Join(dir, "getUsbDevices")
    if err := os.WriteFile(executable, []byte("#!/bin/sh\nprintf '056a:00a8:0108\\n'\n"), 0700); err != nil { t.Fatal(err) }
    present, err := probeSDK(executable)
    if err != nil || !present { t.Fatalf("expected STU-540: present=%v err=%v", present, err) }
    if err := os.WriteFile(executable, []byte("#!/bin/sh\nprintf '056a:00a9:0108\\n'\n"), 0700); err != nil { t.Fatal(err) }
    present, err = probeSDK(executable)
    if err != nil || present { t.Fatalf("other device accepted: present=%v err=%v", present, err) }
}

func TestSDKProbeRejectsRelativeAndMissing(t *testing.T) {
    if ok, err := probeSDK("getUsbDevices"); ok || err == nil { t.Fatal("relative command must fail closed") }
    if ok, err := probeSDK(filepath.Join(t.TempDir(), "missing")); ok || err == nil { t.Fatal("missing command must fail closed") }
    if ok, err := probeSDK(""); ok || err != nil { t.Fatal("unconfigured SDK probe must not be an error") }
}
