package main

// Filesystem-backed, one-time ticket replay protection for a SINGLE enrolled
// workstation. Atomic O_EXCL creation survives connector process restarts.
// This does not provide multi-workstation global replay protection, and
// is not activated by any HTTP endpoint.
import (
    "crypto/sha256"
    "encoding/hex"
    "errors"
    "fmt"
    "os"
    "path/filepath"
    "strings"
    "syscall"
)

type filePreviewReplayStore struct {
    directory string
}

// newFilePreviewReplayStore requires a preprovisioned, privately owned
// directory: the connector MUST NOT silently create storage under /tmp.
// Parent-directory trust and disk durability are host provisioning concerns.
func newFilePreviewReplayStore(directory string) (*filePreviewReplayStore, error) {
    if !filepath.IsAbs(directory) || filepath.Clean(directory) != directory {
        return nil, errors.New("Wacom replay directory must be an absolute clean path")
    }
    if err := checkPrivateReplayDirectory(directory); err != nil { return nil, err }
    return &filePreviewReplayStore{directory: directory}, nil
}

func checkPrivateReplayDirectory(directory string) error {
    stat, err := os.Lstat(directory)
    if err != nil { return fmt.Errorf("Wacom replay directory unavailable: %w", err) }
    if stat.Mode()&os.ModeSymlink != 0 || !stat.IsDir() || stat.Mode().Perm() != 0700 {
        return errors.New("Wacom replay directory must be a real private directory (0700)")
    }
    raw, ok := stat.Sys().(*syscall.Stat_t)
    if !ok || raw.Uid != uint32(os.Geteuid()) {
        return errors.New("Wacom replay directory must be owned by connector user")
    }
    return nil
}

// ConsumeOnce is an atomic on-disk create. The hashed filename ensures that
// the ticket's JTI cannot control a filesystem path or leak via filenames.
// Records deliberately remain until an offline, expiration-aware maintenance
// procedure removes them. Never delete a record before all possible ticket
// expiry windows elapse. Filesystem errors consume no authorization.
func (s *filePreviewReplayStore) ConsumeOnce(jti string, expiresAt int64) (bool, error) {
    if s == nil || len(jti) < 20 || len(jti) > 128 || expiresAt <= 0 ||
        strings.ContainsAny(jti, "\r\n\x00") {
        return false, errors.New("invalid replay ticket identifier")
    }
    if err := checkPrivateReplayDirectory(s.directory); err != nil { return false, err }
    digest := sha256.Sum256([]byte(jti))
    key := hex.EncodeToString(digest[:])
    name := filepath.Join(s.directory, key+".used")
    file, err := os.OpenFile(name, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
    if errors.Is(err, os.ErrExist) { return false, nil }
    if err != nil { return false, fmt.Errorf("cannot consume Wacom preview ticket: %w", err) }
    // A partially written file must remain consumed (fail closed).
    _, writeErr := fmt.Fprintf(file, "%d\n", expiresAt)
    syncErr := file.Sync()
    closeErr := file.Close()
    if writeErr != nil || syncErr != nil || closeErr != nil {
        return false, errors.New("Wacom replay record could not be durably committed")
    }
    dir, err := os.Open(s.directory)
    if err != nil { return false, errors.New("cannot sync Wacom replay directory") }
    syncErr = dir.Sync()
    closeErr = dir.Close()
    if syncErr != nil || closeErr != nil {
        return false, errors.New("Wacom replay directory durability unavailable")
    }
    return true, nil
}
