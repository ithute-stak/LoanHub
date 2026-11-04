package main

import (
    "strings"
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
