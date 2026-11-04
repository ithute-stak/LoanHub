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
    source := `#!/bin/sh
printf 'Connected!\n'
printf '1 1 100 200 300 400 1\n'
printf '1 1 101 201 301 401 2\n'
sleep 2
`
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

func TestReadySignalDoesNotExposePenData(t *testing.T) {
    invoked := 0
    input := strings.NewReader("Connected!\n(use stylus, press CTRL-C to quit)\n1 1 100 200 300 400 1\n")
    counts, err := summarizeSampleCountsWithReady(input, 10, func() { invoked++ })
    if err != nil || invoked != 1 || counts.reports != 1 || counts.other != 2 {
        t.Fatalf("ready=%d counts=%+v error=%v", invoked, counts, err)
    }
}

func TestReadinessIsNotMistakenForPenContact(t *testing.T) {
    ready := 0
    text := "Connected!\n(use stylus, press CTRL-C to quit)\nrdy sw x y pres time seq\n"
    counts, err := summarizeSampleCountsWithReady(strings.NewReader(text), 10, func() { ready++ })
    if err != nil || !counts.ready || ready != 1 || counts.reports != 0 || counts.contactReports != 0 {
        t.Fatalf("startup must not count as pen: counts=%+v ready=%d err=%v", counts, ready, err)
    }
}

func TestContactCountsExcludeHoverAndPenUp(t *testing.T) {
    stream := "1 0 0 9000 2000 1000 1\n1 1 120 9000 2000 1005 2\n1 1 120 9001 2001 1010 3\n1 0 0 9002 2002 1015 4\n"
    counts, err := summarizeSampleCounts(strings.NewReader(stream), 10)
    if err != nil || counts.reports != 4 || counts.contactReports != 2 {
        t.Fatalf("incorrect pen contact accounting: %+v %v", counts, err)
    }
}
