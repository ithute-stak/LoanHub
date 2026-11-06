package main

import (
    "bytes"
    "image/png"
    "testing"
)

func syntheticWacomCalibration() deviceCalibration {
    return deviceCalibration{MaxX:20000,MaxY:10000,MaxPressure:1023}
}

func TestDisposablePNGDrawsSeparateStrokes(t *testing.T) {
    reports:=[]penSample{
        {Ready:1,Switch:1,Pressure:300,X:1000,Y:1000},
        {Ready:1,Switch:1,Pressure:300,X:2000,Y:2000},
        {Ready:1,Switch:1,Pressure:300,X:3000,Y:3000},
        {Ready:1,Switch:0,Pressure:0,X:3000,Y:3000},
        {Ready:1,Switch:1,Pressure:300,X:15000,Y:7000},
        {Ready:1,Switch:1,Pressure:300,X:16000,Y:8000},
    }
    result,err:=renderDisposableWacomPNG(reports,syntheticWacomCalibration())
    if err!=nil {t.Fatal(err)}
    if result.ContactPoints!=5 || result.StrokeCount!=2 {
        t.Fatalf("unexpected stroke count %+v",result)
    }
    img,err:=png.Decode(bytes.NewReader(result.PNG))
    if err!=nil {t.Fatal(err)}
    if img.Bounds().Dx()!=wacomPreviewWidth || img.Bounds().Dy()!=wacomPreviewHeight {
        t.Fatal("invalid image bounds")
    }
    if result.SHA256=="" || len(result.PNG)>wacomPreviewMaxBytes {
        t.Fatal("missing digest or oversize PNG")
    }
}

func TestDisposablePNGRejectsInvalidStrokes(t *testing.T) {
    c:=syntheticWacomCalibration()
    cases:=[][]penSample{
        nil,
        {{Ready:1,Switch:0,Pressure:0,X:100,Y:100}},
        {{Ready:1,Switch:1,Pressure:500,X:10,Y:10}},
        {
            {Ready:1,Switch:1,Pressure:500,X:10,Y:10},
            {Ready:1,Switch:1,Pressure:500,X:10,Y:10},
            {Ready:1,Switch:1,Pressure:500,X:10,Y:10},
        },
        {
            {Ready:1,Switch:1,Pressure:500,X:10,Y:10},
            {Ready:1,Switch:1,Pressure:500,X:20,Y:20},
            {Ready:1,Switch:1,Pressure:500,X:30000,Y:30},
        },
        {
            {Ready:1,Switch:1,Pressure:500,X:10,Y:10},
            {Ready:1,Switch:1,Pressure:500,X:20,Y:20},
            {Ready:1,Switch:1,Pressure:5000,X:30,Y:30},
        },
    }
    for i,reports:=range cases {
        if _,err:=renderDisposableWacomPNG(reports,c);err==nil {
            t.Fatalf("accepted invalid capture #%d",i)
        }
    }
}

func TestDisposablePNGRejectsInvalidCalibration(t *testing.T) {
    reports:=[]penSample{
        {Ready:1,Switch:1,Pressure:500,X:10,Y:10},
        {Ready:1,Switch:1,Pressure:500,X:20,Y:20},
        {Ready:1,Switch:1,Pressure:500,X:30,Y:30},
    }
    if _,err:=renderDisposableWacomPNG(reports,deviceCalibration{});err==nil {
        t.Fatal("accepted missing calibration")
    }
}

func TestDisposablePNGRejectsSampleFlood(t *testing.T) {
    reports:=make([]penSample,wacomPreviewMaxSamples+1)
    if _,err:=renderDisposableWacomPNG(reports,syntheticWacomCalibration());err==nil {
        t.Fatal("accepted unbounded samples")
    }
}
