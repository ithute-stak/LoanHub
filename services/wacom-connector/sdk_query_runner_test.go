package main

import (
    "os"
    "path/filepath"
    "testing"
    "strings"
)

func TestLocalSDKQueryWithSyntheticExecutable(t *testing.T) {
    dir := t.TempDir()
    path := filepath.Join(dir, "query")
    // No Wacom hardware is touched by this synthetic executable.
    fixture := "#!/bin/sh\nprintf 'Capability.tabletMaxX       10800\\nCapability.tabletMaxY       6480\\nCapability.tabletMaxPressure       1023\\n'\n"
    if err := os.WriteFile(path, []byte(fixture), 0700); err != nil { t.Fatal(err) }
    got,err := queryLocalSDKCalibration(path)
    if err != nil { t.Fatal(err) }
    if got.MaxX != 10800 || got.MaxY != 6480 || got.MaxPressure != 1023 {
        t.Fatalf("bad calibration: %+v",got)
    }
}

func TestSDKQueryRejectsInvalidAndOversizedOutput(t *testing.T) {
    dir:=t.TempDir()
    fail:=filepath.Join(dir,"fail")
    if err:=os.WriteFile(fail,[]byte("#!/bin/sh\nexit 2\n"),0700);err!=nil {t.Fatal(err)}
    if _,err:=queryLocalSDKCalibration(fail);err==nil {t.Fatal("accepted failed query process")}
    overflow:=&boundedOutput{max:3}
    n,err:=overflow.Write([]byte("abcdefgh"))
    if err!=nil || n!=8 || !overflow.overflow || overflow.buf.String()!="abc" { t.Fatal("unbounded output") }
    if _,err:=queryLocalSDKCalibration("relative-query");err==nil {t.Fatal("accepted relative executable")}
    noCaps:=filepath.Join(dir,"empty")
    if err:=os.WriteFile(noCaps,[]byte("#!/bin/sh\nprintf 'No USB devices found\\n'\n"),0700);err!=nil {t.Fatal(err)}
    if _,err:=queryLocalSDKCalibration(noCaps);err==nil {t.Fatal("accepted missing capabilities")}
}

func TestSDKQueryExplainsLibusbBusyEvenOnZeroExit(t *testing.T) {
    dir := t.TempDir()
    executable := filepath.Join(dir, "query-busy")
    content := "#!/bin/sh\nprintf 'STU query sample\\nDevice: 056a:00a8:0108\\nFailed to connect:libusb:-6\\n'\n"
    if err := os.WriteFile(executable, []byte(content), 0700); err != nil { t.Fatal(err) }
    _, err := queryLocalSDKCalibration(executable)
    if err == nil || !strings.Contains(err.Error(), "busy") {
        t.Fatalf("expected explicit device busy error, got %v", err)
    }
}
