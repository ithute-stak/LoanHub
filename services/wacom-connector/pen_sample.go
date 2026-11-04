package main

import (
    "bufio"
    "context"
    "errors"
    "fmt"
    "io"
    "log"
    "os"
    "os/exec"
    "path/filepath"
    "strconv"
    "regexp"
    "syscall"
    "strings"
    "time"
)

// The official Wacom SDK simpleInterface emits seven numeric values in the
// order rdy, sw, pressure, x, y, time, sequence. Its displayed column header
// is misleading: observed rows such as '1 0 0 10091 4944 8160 1' would
// otherwise imply impossible pressure 4944 (> device maximum 1023).
// Values are NOT signature evidence.
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
        Ready: values[0], Switch: values[1], Pressure: values[2],
        X: values[3], Y: values[4], Time: values[5], Sequence: values[6],
    }, true
}

// summarizeSamples discards raw pen coordinates, pressure, timestamps and
// sequence numbers. The summary is for local hardware diagnostics only.
type sampleCounts struct {
    reports int
    lines int
    other int
    ready bool
    contactReports int
}

// Count only. Neither the report coordinates nor rejected lines are logged.
// When the SDK fails, diagnostics distinguish no output from non-pen output.
func summarizeSampleCounts(source io.Reader, maxLines int) (sampleCounts, error) {
    return summarizeSampleCountsWithReady(source, maxLines, nil)
}

// onReady is invoked once when the official SDK sample instructs the operator
// to use the stylus. No capture point data is logged.
func summarizeSampleCountsWithReady(source io.Reader, maxLines int, onReady func()) (sampleCounts, error) {
    return summarizeSampleCountsWithHandler(source, maxLines, onReady, nil)
}

// onPen runs only on numeric SDK reports. It must not log, serialize or
// transmit coordinate data. Callback errors fail closed.
func summarizeSampleCountsWithHandler(source io.Reader, maxLines int, onReady func(), onPen func(penSample) error) (sampleCounts, error) {
    var counts sampleCounts
    if maxLines < 1 || maxLines > 10000 {
        return counts, errors.New("invalid line budget")
    }
    scanner := bufio.NewScanner(source)
    scanner.Buffer(make([]byte, 4096), 4096)
    ready := false
    for scanner.Scan() {
        if !ready && strings.Contains(scanner.Text(), "use stylus") {
            ready = true
            counts.ready = true
            if onReady != nil { onReady() }
        }
        counts.lines++
        if counts.lines > maxLines {
            return sampleCounts{}, errors.New("Wacom diagnostic output limit exceeded")
        }
        if report, ok := parsePenSample(scanner.Text()); ok {
            counts.reports++
            if report.Ready == 1 && report.Switch == 1 { counts.contactReports++ }
            if onPen != nil {
                if err := onPen(report); err != nil { return counts, err }
            }
        } else {
            counts.other++
        }
    }
    return counts, scanner.Err()
}

func summarizeSamples(source io.Reader, maxLines int) (int, error) {
    counts, err := summarizeSampleCounts(source, maxLines)
    return counts.reports, err
}

type countingWriter struct { count int }
func (w *countingWriter) Write(p []byte) (int, error) {
    w.count += len(p)
    return len(p), nil
}

// testWacomPenSample is explicitly operator-initiated, bounded and local.
// It launches the vendor SDK sample only, never a shell or user-selected
// command from an HTTP request. The vendor sample is killed at timeout.
// Output is discarded except for counts, and never crosses localhost.
var safeSamplePath = regexp.MustCompile(`^/[A-Za-z0-9_./-]+$`)


// isOperatorTerminalStdin recognizes Linux controlling terminal fds without
// reading input or invoking an external process. A /dev/null stdin must not
// be mistaken for an interactive terminal. Only used for the local CLI.
func isOperatorTerminalStdin() bool {
    target, err := os.Readlink("/proc/self/fd/0")
    return err == nil && (strings.HasPrefix(target, "/dev/pts/") || target == "/dev/tty" || strings.HasPrefix(target, "/dev/tty"))
}

func testWacomPenSample(executable string, duration time.Duration) (int, error) {
    return testWacomSampleWithHandler(executable, duration, nil)
}

func testWacomSampleWithHandler(executable string, duration time.Duration, onPen func(penSample) error) (int, error) {
    if !filepath.IsAbs(executable) || !safeSamplePath.MatchString(executable) {
        return 0, errors.New("sample executable path must be absolute and contain no shell metacharacters")
    }
    if duration < time.Second || duration > 30*time.Second { return 0, errors.New("invalid diagnostic duration") }
    stat, err := os.Stat(executable)
    if err != nil { return 0, err }
    if !stat.Mode().IsRegular() || stat.Mode().Perm()&0111 == 0 {
        return 0, errors.New("sample is not an executable file")
    }
    ctx, cancel := context.WithTimeout(context.Background(), duration)
    defer cancel()
    // The Wacom C++ sample emits reports immediately to a terminal, but
    // buffers its stdout when piped. A pseudo-terminal restores that behavior.
    // util-linux script runs a local, strictly validated executable path.
    // This is only a CLI diagnostic: no HTTP caller controls this path.
    script, err := exec.LookPath("script")
    if err != nil { return 0, fmt.Errorf("util-linux script required: %w", err) }
    command := exec.CommandContext(ctx, script, "-q", "-f", "-e", "-c", "exec "+executable, "/dev/null")
    // Reproduce the known-working operator pipeline:
    //   script ... /dev/null | awk ...
    // The operator's *real TTY stdin* is inherited by script while its
    // output is piped. Our previous synthetic os.Pipe stdin allowed the
    // SDK to initialize but repeatedly returned zero pen events. For
    // noninteractive CI mock tests, keep the prior open-pipe fallback.
    var stdinReader, stdinWriter *os.File
    if isOperatorTerminalStdin() {
        command.Stdin = os.Stdin
    } else {
        stdinReader, stdinWriter, err = os.Pipe()
        if err != nil { return 0, err }
        defer stdinReader.Close()
        defer stdinWriter.Close()
        command.Stdin = stdinReader
    }
    command.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
    // On deadline, request orderly PTY shutdown before the final forced kill.
    command.Cancel = func() error { return syscall.Kill(-command.Process.Pid, syscall.SIGTERM) }
    command.WaitDelay = 2 * time.Second
    pipe, err := command.StdoutPipe()
    if err != nil { return 0, err }
    // Avoid collecting or printing pen coordinates to logs.
    // Count vendor stderr bytes only; never expose its content or pen samples.
    diagnosticErr := &countingWriter{}
    command.Stderr = diagnosticErr
    if err := command.Start(); err != nil { return 0, err }
    // The child has inherited its stdin file descriptor; parent can drop its
    // reader copy while retaining the writer to prevent an early EOF.
    if stdinReader != nil { _ = stdinReader.Close() }
    // CommandContext kills the PTY parent on timeout. Ensure any vendor
    // child in the separate process group is also terminated.
    defer func() { _ = syscall.Kill(-command.Process.Pid, syscall.SIGKILL) }()
    // A descendant can keep the PTY output pipe open after script exits.
    // Explicitly close our reader on the deadline to avoid indefinite hangs.
    readerClosed := make(chan struct{})
    go func() {
        select {
        case <-ctx.Done():
            _ = pipe.Close()
        case <-readerClosed:
        }
    }()
    counts, parseErr := summarizeSampleCountsWithHandler(pipe, 10000, func() {
        log.Println("Wacom SDK ready: draw TEST strokes on the STU-540 now.")
    }, onPen)
    close(readerClosed)
    waitErr := command.Wait()
    if parseErr != nil && ctx.Err() == nil { return 0, parseErr }
    if counts.reports == 0 {
        return 0, fmt.Errorf("no pen reports: sdk_ready=%t, %d stdout lines, %d non-report lines, %d stderr bytes, exit=%v (values not recorded)", counts.ready, counts.lines, counts.other, diagnosticErr.count, waitErr)
    }
    if ctx.Err() != nil && !errors.Is(ctx.Err(), context.DeadlineExceeded) {
        return 0, ctx.Err()
    }
    if waitErr != nil && !errors.Is(ctx.Err(), context.DeadlineExceeded) {
        return 0, fmt.Errorf("vendor pen sample exited unsuccessfully: %w", waitErr)
    }
    log.Printf("Wacom diagnostic: sdk_ready=%t, %d total pen reports, %d pen-contact reports.", counts.ready, counts.reports, counts.contactReports)
    return counts.reports, nil
}
