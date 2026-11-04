package main

import (
    "bytes"
    "context"
    "errors"
    "fmt"
    "os"
    "os/exec"
    "path/filepath"
    "time"
)

// Query only via explicit local CLI invocation. Never exposed on localhost
// HTTP or authorized as evidence of a borrower/contract signing.
func queryLocalSDKCalibration(executable string) (deviceCalibration, error) {
    if !filepath.IsAbs(executable) || !safeSamplePath.MatchString(executable) {
        return deviceCalibration{}, errors.New("SDK query executable must be an absolute safe path")
    }
    info, err := os.Stat(executable)
    if err != nil { return deviceCalibration{}, err }
    if !info.Mode().IsRegular() || info.Mode().Perm()&0111 == 0 {
        return deviceCalibration{}, errors.New("SDK query path is not executable")
    }
    ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
    defer cancel()
    command := exec.CommandContext(ctx, executable)
    command.Stdin = nil
    // Fail rather than accumulating unbounded output from a faulty executable.
    stdout := &boundedOutput{max:128*1024}
    stderr := &boundedOutput{max:16*1024}
    command.Stdout = stdout
    command.Stderr = stderr
    runErr := command.Run()
    if ctx.Err() != nil { return deviceCalibration{}, fmt.Errorf("SDK query timed out or was cancelled: %w",ctx.Err()) }
    if stdout.overflow || stderr.overflow { return deviceCalibration{}, errors.New("SDK query output exceeded safe limit") }
    if runErr != nil {
        return deviceCalibration{}, fmt.Errorf("SDK query failed (output withheld): %w",runErr)
    }
    return parseSDKQueryCalibration(bytes.NewReader(stdout.buf.Bytes()))
}

type boundedOutput struct {
    buf bytes.Buffer
    max int
    overflow bool
}
func (w *boundedOutput) Write(p []byte) (int,error) {
    if w.overflow { return len(p), nil }
    available:=w.max-w.buf.Len()
    if len(p)>available {
        if available>0 { _,_ = w.buf.Write(p[:available]) }
        w.overflow=true
        return len(p),nil
    }
    _,_ = w.buf.Write(p)
    return len(p),nil
}
