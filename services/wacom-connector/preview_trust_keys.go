package main

// The connector's backend Ed25519 verification keys must be independently
// provisioned by a trusted workstation administrator. Never download public
// keys in response to a browser request or use an unverified JWT "jku".
import (
    "bytes"
    "crypto/ed25519"
    "encoding/base64"
    "encoding/json"
    "errors"
    "fmt"
    "io"
    "os"
    "path/filepath"
    "regexp"
    "syscall"
)

const maxWacomTrustFileBytes = 16 * 1024

var trustKeyID = regexp.MustCompile(`^[A-Za-z0-9_-]{1,64}$`)

type wacomTrustFile struct {
    Version int `json:"version"`
    Keys []struct {
        ID string `json:"id"`
        PublicKey string `json:"public_key_base64"`
    } `json:"keys"`
}

// loadPinnedWacomPreviewKeys reads a locally provisioned, non-symlink
// private trust file, owned by the invoking service account. This is a
// loader only and is not connected to the public connector HTTP server.
func loadPinnedWacomPreviewKeys(path string) (map[string]ed25519.PublicKey, error) {
    if !filepath.IsAbs(path) || filepath.Clean(path) != path {
        return nil, errors.New("Wacom trust file requires absolute clean path")
    }
    // For a single-workstation deployment, the config directory itself
    // is private and owned by the connector OS user. Its parent must be
    // provisioned securely by host administration.
    parent := filepath.Dir(path)
    parentInfo, err := os.Lstat(parent)
    if err != nil { return nil, fmt.Errorf("Wacom trust directory unavailable: %w", err) }
    if parentInfo.Mode()&os.ModeSymlink != 0 || !parentInfo.IsDir() ||
        parentInfo.Mode().Perm() != 0700 || !ownedByConnectorUser(parentInfo) {
        return nil, errors.New("Wacom trust directory must be private, owned, non-symlink (0700)")
    }
    info, err := os.Lstat(path)
    if err != nil { return nil, fmt.Errorf("Wacom trust file unavailable: %w", err) }
    if !info.Mode().IsRegular() || info.Mode().Perm() != 0600 || !ownedByConnectorUser(info) ||
        info.Size() <= 0 || info.Size() > maxWacomTrustFileBytes {
        return nil, errors.New("Wacom trust file must be owned regular file (0600), with bounded size")
    }
    file, err := os.OpenFile(path, os.O_RDONLY|syscall.O_NOFOLLOW, 0)
    if err != nil { return nil, fmt.Errorf("cannot safely open Wacom trust file: %w", err) }
    defer file.Close()
    opened, err := file.Stat()
    if err != nil || !opened.Mode().IsRegular() || opened.Mode().Perm() != 0600 ||
        !ownedByConnectorUser(opened) || !os.SameFile(info, opened) {
        return nil, errors.New("Wacom trust file changed during open")
    }

    raw, err := io.ReadAll(io.LimitReader(file, maxWacomTrustFileBytes+1))
    if err != nil || len(raw) > maxWacomTrustFileBytes {
        return nil, errors.New("Wacom trust file cannot be read safely")
    }
    decoder := json.NewDecoder(bytes.NewReader(raw))
    decoder.DisallowUnknownFields()
    var data wacomTrustFile
    if err := decoder.Decode(&data); err != nil { return nil, fmt.Errorf("invalid Wacom trust file: %w", err) }
    if err := decoder.Decode(new(any)); err != io.EOF {
        return nil, errors.New("Wacom trust file contains trailing data")
    }
    if data.Version != 1 || len(data.Keys) < 1 || len(data.Keys) > 8 {
        return nil, errors.New("invalid Wacom public-key trust bundle")
    }
    keys := make(map[string]ed25519.PublicKey, len(data.Keys))
    for _, entry := range data.Keys {
        if !trustKeyID.MatchString(entry.ID) { return nil, errors.New("invalid Wacom key id") }
        if _, exists := keys[entry.ID]; exists { return nil, errors.New("duplicate Wacom public-key id") }
        decoded, err := base64.StdEncoding.Strict().DecodeString(entry.PublicKey)
        if err != nil || len(decoded) != ed25519.PublicKeySize {
            return nil, errors.New("invalid Wacom Ed25519 public key")
        }
        keys[entry.ID] = ed25519.PublicKey(decoded)
    }
    return keys, nil
}

func ownedByConnectorUser(info os.FileInfo) bool {
    raw, ok := info.Sys().(*syscall.Stat_t)
    return ok && raw.Uid == uint32(os.Geteuid())
}
