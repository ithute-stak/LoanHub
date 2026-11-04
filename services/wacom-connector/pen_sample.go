package main

import (
    "bufio"
    "context"
    "errors"
    "fmt"
    "io"
    "os"
    "os/exec"
    "path/filepath"
    "strconv"
    "strings"
    "time"
)

// Wacom SDK simpleInterface diagnostic output contains seven numeric columns:
// rdy sw x y pres time seq. Values are UNCALIBRATED, NOT signature evidence.
// This code deliberately does not export, render or persist handwriting.
type penSample struct {
    Ready int
    Switch int
    X int
    Y int
    Pressure int
    Time int
    Sequence int
}

func parsePenSample(line string) (penSample, bool) {
    fields := strings.Fields(line)
    if len(fields) != 7 { return penSample{}, false }
    values := [7]int{}
    for i, field := range fields {
        value, err := strconv.Atoi(field)
        if err != nil || value < 0 || value > 1_000_000_000 { return penSample{}, false }
        values[i] = value
    }
    if values[0] > 1 || values[1] > 1 { return penSample{}, false }
    return penSample{
        Ready: values[0], Switch: values[1], X: values[2], Y: values[3],
        Pressure: values[4], Time: values[5], Sequence: values[6],
    }, true
}

// summarizeSamples discards raw pen coordinates, pressure, timestamps and
// sequence numbers. The summary is for local hardware diagnostics only.
func summarizeSamples(source io.Reader, maxLines int) (int, error) {
    if maxLines < 1 || maxLines > 10000 { return 0, errors.New("invalid line budget") }
    scanner := bufio.NewScanner(source)
    scanner.Buffer(make([]byte, 4096), 4096)
    count := 0
    lines := 0
    for scanner.Scan() {
        lines++
        if lines > maxLines { return 0, errors.New("Wacom diagnostic output limit exceeded") }
        if _, ok := parsePenSample(scanner.Text()); ok { count++ }
    }
    return count, scanner.Err()
}

// testWacomPenSample is explicitly operator-initiated, bounded and local.
// It launches the vendor SDK sample only, never a shell or user-selected
// command from an HTTP request. The vendor sample is killed at timeout.
// Output is discarded except for counts, and never crosses localhost.
func testWacomPenSample(executable string, duration time.Duration) (int, error) {
    if !filepath.IsAbs(executable) { return 0, errors.New("sample executable path must be absolute") }
    if duration < time.Second || duration > 15*time.Second { return 0, errors.New("invalid diagnostic duration") }
    stat, err := os.Stat(executable)
    if err != nil { return 0, err }
    if !stat.Mode().IsRegular() || stat.Mode().Perm()&0111 == 0 {
        return 0, errors.New("sample is not an executable file")
    }
    ctx, cancel := context.WithTimeout(context.Background(), duration)
    defer cancel()
    // The vendor sample may block-buffer stdout when launched through a pipe.
    // Request line buffering without using a shell or reading pen data into logs.
    stdbuf, err := exec.LookPath("stdbuf")
    if err != nil { return 0, fmt.Errorf("coreutils stdbuf required: %w", err) }
    command := exec.CommandContext(ctx, stdbuf, "-oL", executable)
    pipe, err := command.StdoutPipe()
    if err != nil { return 0, err }
    // Avoid collecting or printing pen coordinates to logs.
    command.Stderr = io.Discard
    if err := command.Start(); err != nil { return 0, err }
    count, parseErr := summarizeSamples(pipe, 10000)
    waitErr := command.Wait()
    if parseErr != nil { return 0, parseErr }
    if ctx.Err() != nil && !errors.Is(ctx.Err(), context.DeadlineExceeded) {
        return 0, ctx.Err()
    }
    if waitErr != nil && !errors.Is(ctx.Err(), context.DeadlineExceeded) {
        return 0, fmt.Errorf("vendor pen sample exited unsuccessfully: %w", waitErr)
    }
    return count, nil
}
