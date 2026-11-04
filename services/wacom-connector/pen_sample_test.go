package main

import (
    "strings"
    "os"
    "os/exec"
    "path/filepath"
    "testing"
    "time"
)

func TestParseVendorSample(t *testing.T) {
    sample, ok := parsePenSample("  1   0     0  6093  3975 14080     1")
    if !ok || sample.Ready != 1 || sample.Y != 6093 || sample.Pressure != 3975 || sample.Sequence != 1 {
        t.Fatalf("vendor sample did not parse correctly: %+v, %t", sample, ok)
    }
}

func TestRejectNonPenAndMalformedLines(t *testing.T) {
    for _, line := range []string{
        "No TLS devices found", "Connecting to first device found: 056a:00a8:0108",
        "rdy sw x y pres time seq", "1 0 3 4 5 6",
        "1 0 3 -1 5 6 7", "0 2 3 4 5 6 7", "1 0 nan 4 5 6 7",
    } {
        if _, ok := parsePenSample(line); ok { t.Errorf("accepted %q", line) }
    }
}

func TestOnlyAggregatedCountsAreReturned(t *testing.T) {
    count, err := summarizeSamples(strings.NewReader("Connected!\n1 0 0 6093 3975 14080 1\n1 0 0 6093 3975 14085 2\n"), 10)
    if err != nil || count != 2 { t.Fatalf("count=%d error=%v", count, err) }
}

func TestFailClosedOnOutputLimit(t *testing.T) {
    _, err := summarizeSamples(strings.NewReader("a\nb\nc\n"), 2)
    if err == nil { t.Fatal("expected output limit to reject") }
}

func TestNoArbitraryRelativeCommandsOrUnboundedTest(t *testing.T) {
    if _, err := testWacomPenSample("./simpleInterface", 5*time.Second); err == nil {
        t.Fatal("relative sample path allowed")
    }
    if _, err := testWacomPenSample("/missing/wacom/sample", time.Hour); err == nil {
        t.Fatal("unbounded diagnostic duration allowed")
    }
}

func TestSamplePathRejectsShellMetacharacters(t *testing.T) {
    for _, value := range []string{
        "/tmp/a b", "/tmp/a;touch", "/tmp/a$(id)", "/tmp/a'bad", "/tmp/a\"bad",
    } {
        if safeSamplePath.MatchString(value) {
            t.Errorf("shell-unsafe executable path was accepted: %q", value)
        }
    }
    if !safeSamplePath.MatchString("/home/selemela/wacom-stu-sdk/sdk-extracted/Linux/x86_64/simpleInterface") {
        t.Fatal("actual SDK executable path rejected")
    }
}

func TestDiagnosticCountsSilentAndUnrecognizedOutputSeparately(t *testing.T) {
    quiet, err := summarizeSampleCounts(strings.NewReader(""), 10)
    if err != nil || quiet.lines != 0 || quiet.reports != 0 {
        t.Fatalf("quiet count: %+v %v", quiet, err)
    }
    noisy, err := summarizeSampleCounts(strings.NewReader(
        "Connecting...\nConnected!\n1 1 105 250 300 400 1\n"), 10)
    if err != nil || noisy.lines != 3 || noisy.other != 2 || noisy.reports != 1 {
        t.Fatalf("noisy count: %+v %v", noisy, err)
    }
}

func TestPTYReceivesFakeVendorOutputWithoutEarlyStdinEOF(t *testing.T) {
    if _, err := exec.LookPath("script"); err != nil {
        t.Skip("util-linux script unavailable on test host")
    }
    sample := filepath.Join(t.TempDir(), "fake-simpleInterface")
    // A mock vendor executable that prints a few numeric lines before
    // sleeping. No Wacom hardware or borrower data is involved.
    source := "#!/bin/sh\\nprintf 'Connected!\\\\n'\\nprintf '1 1 100 200 300 400 1\\\\n'\\nprintf '1 1 101 201 301 401 2\\\\n'\\nsleep 2\\n"
    if err := os.WriteFile(sample, []byte(source), 0700); err != nil {
        t.Fatal(err)
    }
    count, err := testWacomPenSample(sample, 1200*time.Millisecond)
    if err != nil {
        t.Fatalf("PTY did not deliver mock vendor lines: %v", err)
    }
    if count != 2 {
        t.Fatalf("expected two mock numeric reports, got %d", count)
    }
}
