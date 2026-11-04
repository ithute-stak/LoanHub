package main

import (
    "bufio"
    "errors"
    "fmt"
    "io"
    "regexp"
    "strconv"
    "strings"
)

// The official Wacom Linux STU SDK includes the `query` executable.
// It prints Capability.tabletMaxX/Y/Pressure from the tablet. This parser
// accepts only the three declared integer capability fields. It does not
// guess from pen coordinates, persist evidence, or enable contract signing.
var capabilityLine = regexp.MustCompile(`^Capability\.(tabletMaxX|tabletMaxY|tabletMaxPressure)\s*(?:=|:)?\s*([0-9]{1,7})\s*$`)

func parseSDKQueryCalibration(source io.Reader) (deviceCalibration, error) {
    var values = map[string]int{}
    scanner := bufio.NewScanner(io.LimitReader(source, 128*1024))
    scanner.Buffer(make([]byte, 2048), 8192)
    lines := 0
    for scanner.Scan() {
        lines++
        if lines > 2500 { return deviceCalibration{}, errors.New("SDK query exceeded line budget") }
        line := strings.TrimSpace(strings.TrimSuffix(scanner.Text(), "\r"))
        parts := capabilityLine.FindStringSubmatch(line)
        if parts == nil { continue }
        value, err := strconv.Atoi(parts[2])
        if err != nil { return deviceCalibration{}, errors.New("invalid SDK capability integer") }
        if _, exists := values[parts[1]]; exists {
            return deviceCalibration{}, fmt.Errorf("duplicate SDK capability %s", parts[1])
        }
        values[parts[1]] = value
    }
    if err := scanner.Err(); err != nil { return deviceCalibration{}, fmt.Errorf("SDK capability scan failed: %w", err) }
    if len(values) != 3 {
        return deviceCalibration{}, errors.New("SDK query missing tabletMaxX, tabletMaxY or tabletMaxPressure")
    }
    c := deviceCalibration{
        MaxX: values["tabletMaxX"], MaxY: values["tabletMaxY"],
        MaxPressure: values["tabletMaxPressure"],
    }
    if !c.valid() { return deviceCalibration{}, errors.New("SDK returned unsafe tablet calibration values") }
    return c, nil
}
