package main

import (
    "errors"
    "strings"
    "testing"
)

func TestParseSDKStreamIntoPrivateStrokeBuffer(t *testing.T) {
    var b localStrokeBuffer
    defer b.discard()
    sample := strings.Join([]string{
        "STU simpleInterface sample",
        "(use stylus, press CTRL-C to quit)",
        "rdy sw x y pres time seq",
        "1 0 0 9000 2000 1000 1",
        "1 1 115 9000 2000 1005 2",
        "1 1 130 8998 2001 1010 3",
        "1 0 0 8998 2001 1015 4",
        "1 1 125 8900 2100 1020 5",
        "1 1 150 8800 2200 1025 6",
    }, "\n") + "\n"
    ready := 0
    counts, err := summarizeSampleCountsWithHandler(
        strings.NewReader(sample), 20, func() { ready++ }, b.accept,
    )
    if err != nil { t.Fatal(err) }
    strokes, err := b.finish()
    if err != nil { t.Fatal(err) }
    if ready != 1 || counts.reports != 5 || b.count != 4 || len(strokes) != 2 {
        t.Fatalf("ready=%d reports=%d points=%d strokes=%d", ready, counts.reports, b.count, len(strokes))
    }
}

func TestSDKCallbackFailureStopsParsing(t *testing.T) {
    callbacks := 0
    counts, err := summarizeSampleCountsWithHandler(strings.NewReader(
        "1 1 100 200 300 400 1\n1 1 101 201 301 401 2\n",
    ), 10, nil, func(p penSample) error {
        callbacks++
        return errors.New("capture rejected")
    })
    if err == nil || callbacks != 1 || counts.reports != 1 {
        t.Fatalf("failed closed: error=%v callbacks=%d counts=%+v", err, callbacks, counts)
    }
}
