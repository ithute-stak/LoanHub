package main

import (
    "context"
    "errors"
    "os"
    "os/exec"
    "path/filepath"
    "regexp"
    "time"
)

// SDK presence is distinct from opening the tablet. Enumerating a device is
// NOT pen capture, proof of user consent or permission to finalize a contract.
var stu540Line = regexp.MustCompile(`(?m)(?:^|[^0-9a-fA-F])056a:00a8:[0-9a-fA-F]{4}(?:$|[^0-9a-fA-F])`)

// probeSDK performs one optional, operator-initiated startup diagnostic.
// The executable must come from the Wacom SDK installed locally and is never
// downloaded, run with shell interpolation or specified by HTTP callers.
func probeSDK(path string) (bool, error) {
    if path == "" { return false, nil }
    if !filepath.IsAbs(path) { return false, errors.New("SDK executable must be an absolute path") }
    info, err := os.Stat(path)
    if err != nil { return false, err }
    if !info.Mode().IsRegular() || info.Mode().Perm()&0111 == 0 {
        return false, errors.New("SDK enumerator is not an executable file")
    }
    ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
    defer cancel()
    cmd := exec.CommandContext(ctx, path)
    output, err := cmd.Output()
    if ctx.Err() != nil { return false, ctx.Err() }
    if err != nil { return false, err }
    if len(output) > 16384 { return false, errors.New("SDK output exceeds diagnostic limit") }
    return stu540Line.Match(output), nil
}
