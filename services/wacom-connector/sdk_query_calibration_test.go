package main

import (
    "strings"
    "testing"
)

func TestParseVendorSDKQueryCapabilities(t *testing.T) {
    // Vendor field names are real; numeric values are synthetic, not device measurements.
    output := "STU query sample\nConnecting...\n" +
        "Capability.tabletMaxX        10800\n" +
        "Capability.tabletMaxY = 6480\n" +
        "Capability.tabletMaxPressure: 1023\n" +
        "Capability.screenWidth 800\nCapability.screenHeight 480\n"
    c, err := parseSDKQueryCalibration(strings.NewReader(output))
    if err != nil { t.Fatal(err) }
    if c.MinX != 0 || c.MinY != 0 || c.MaxX != 10800 || c.MaxY != 6480 || c.MaxPressure != 1023 {
        t.Fatalf("unexpected calibration: %+v", c)
    }
}

func TestRejectsMissingDuplicateOrUnsafeSDKCapabilities(t *testing.T) {
    cases := []string{
        "No USB devices found\n",
        "Capability.tabletMaxX 10800\nCapability.tabletMaxY 6480\n",
        "Capability.tabletMaxX 10800\nCapability.tabletMaxX 10801\nCapability.tabletMaxY 6480\nCapability.tabletMaxPressure 1023\n",
        "Capability.tabletMaxX 0\nCapability.tabletMaxY 6480\nCapability.tabletMaxPressure 1023\n",
        "Capability.tabletMaxX 1000001\nCapability.tabletMaxY 6480\nCapability.tabletMaxPressure 1023\n",
        "Capability.tabletMaxX 10800\nCapability.tabletMaxY 6480\nCapability.tabletMaxPressure 0\n",
        "Capability.tabletMaxX -10800\nCapability.tabletMaxY 6480\nCapability.tabletMaxPressure 1023\n",
    }
    for i, input := range cases {
        if _, err := parseSDKQueryCalibration(strings.NewReader(input)); err == nil {
            t.Fatalf("invalid case %d accepted", i)
        }
    }
}
