package main

import (
    "testing"
)

func report(sw, time, seq int) penSample {
    return penSample{Ready: 1, Switch: sw, X: 120+seq, Y: 9200-seq, Pressure: 100+seq, Time: time, Sequence: seq}
}

func TestAssemblerGroupsPenDownIntoStrokes(t *testing.T) {
    var b localStrokeBuffer
    for _, p := range []penSample{report(1,1000,1),report(1,1005,2),report(0,1010,3),report(1,1015,4),report(1,1020,5)} {
        if err := b.accept(p); err != nil { t.Fatal(err) }
    }
    strokes, err := b.finish()
    if err != nil { t.Fatal(err) }
    if len(strokes) != 2 || len(strokes[0]) != 2 || len(strokes[1]) != 2 {
        t.Fatalf("unexpected stroke partition %+v", strokes)
    }
    if strokes[0][0].Pressure != 101 || strokes[1][0].Sequence != 4 {
        t.Fatal("raw pressure and sequence must be preserved")
    }
    b.discard()
    if strokes[0][0] != (nativePenPoint{}) { t.Fatal("discard must blank out retained slice values") }
}

func TestAssemblerRejectsNonmonotonicOrDuplicateSequence(t *testing.T) {
    var b localStrokeBuffer
    if err := b.accept(report(1,1000,1)); err != nil { t.Fatal(err) }
    if err := b.accept(report(1,1002,1)); err == nil { t.Fatal("duplicate sequence allowed") }
    if err := b.accept(report(1,999,2)); err == nil { t.Fatal("timestamp reversal allowed") }
}

func TestAssemblerLimitsAndSealedState(t *testing.T) {
    var b localStrokeBuffer
    if err := b.accept(report(1,1,1)); err != nil { t.Fatal(err) }
    if err := b.accept(report(1,maxLocalDuration+2,2)); err == nil { t.Fatal("overlong capture accepted") }
    if _, err := b.finish(); err == nil { t.Fatal("one point accepted") }
    if err := b.accept(report(1,2,3)); err == nil { t.Fatal("sealed capture accepted") }
}

func TestAssemblerIgnoresHoverAndRequiresContact(t *testing.T) {
    var b localStrokeBuffer
    if err := b.accept(report(0,10,1)); err != nil { t.Fatal(err) }
    if _, err := b.finish(); err == nil { t.Fatal("hover-only capture accepted") }
}

func TestAssemblerRejectsPointAndStrokeLimits(t *testing.T) {
    var b localStrokeBuffer
    for i:=1; i<=maxLocalPoints; i++ {
        if err := b.accept(report(1,1000+i,i)); err != nil { t.Fatalf("unexpected error at point %d: %v",i,err) }
    }
    if err := b.accept(report(1,11002,10001)); err == nil { t.Fatal("unbounded points accepted") }
    var s localStrokeBuffer
    for i:=1; i<=maxLocalStrokes; i++ {
        if err := s.accept(report(1,1000+2*i,2*i-1)); err != nil { t.Fatal(err) }
        if err := s.accept(report(0,1001+2*i,2*i)); err != nil { t.Fatal(err) }
    }
    if err := s.accept(report(1,2000,1000)); err == nil { t.Fatal("extra stroke accepted") }
}
