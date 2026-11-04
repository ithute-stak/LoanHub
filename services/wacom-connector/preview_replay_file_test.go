package main

import (
    "os"
    "path/filepath"
    "sync"
    "testing"
    "time"
)

func TestFileReplayStorePersistsAcrossReinitialization(t *testing.T) {
    root := t.TempDir()
    dir := filepath.Join(root, "wacom-replay")
    if err := os.Mkdir(dir, 0700); err != nil { t.Fatal(err) }
    store, err := newFilePreviewReplayStore(dir)
    if err != nil { t.Fatal(err) }
    id := "file-ticket-identifier-unique-1234567"
    exp := time.Now().Add(time.Minute).Unix()
    used, err := store.ConsumeOnce(id, exp)
    if err != nil || !used { t.Fatalf("first consume: %v %v", used, err) }
    restarted, err := newFilePreviewReplayStore(dir)
    if err != nil { t.Fatal(err) }
    used, err = restarted.ConsumeOnce(id, exp)
    if err != nil || used { t.Fatalf("replay after restart accepted: %v %v", used, err) }
    files, err := os.ReadDir(dir)
    if err != nil || len(files) != 1 { t.Fatalf("unexpected replay files: %v %v", files, err) }
    if files[0].Name() == id+".used" { t.Fatal("raw JTI leaked into filesystem name") }
}

func TestFileReplayStoreRejectsUnsafeDirectory(t *testing.T) {
    root := t.TempDir()
    dir := filepath.Join(root, "wacom-replay")
    if err := os.Mkdir(dir, 0700); err != nil { t.Fatal(err) }
    if _, err := newFilePreviewReplayStore("relative"); err == nil {
        t.Fatal("relative storage path accepted")
    }
    link := filepath.Join(root, "linked")
    if err := os.Symlink(dir, link); err != nil { t.Fatal(err) }
    if _, err := newFilePreviewReplayStore(link); err == nil {
        t.Fatal("symlink storage path accepted")
    }
    if err := os.Chmod(dir, 0777); err != nil { t.Fatal(err) }
    if _, err := newFilePreviewReplayStore(dir); err == nil {
        t.Fatal("world-accessible replay directory accepted")
    }
}

func TestFileReplayStoreAtomicConcurrentUse(t *testing.T) {
    dir := filepath.Join(t.TempDir(), "wacom-replay")
    if err := os.Mkdir(dir, 0700); err != nil { t.Fatal(err) }
    store, err := newFilePreviewReplayStore(dir)
    if err != nil { t.Fatal(err) }
    const workers = 20
    var wg sync.WaitGroup
    results := make(chan bool, workers)
    for i := 0; i < workers; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            ok, err := store.ConsumeOnce("concurrent-preview-ticket-unique-123", time.Now().Add(time.Minute).Unix())
            if err != nil { t.Errorf("concurrent consume error: %v", err) }
            results <- ok
        }()
    }
    wg.Wait()
    close(results)
    accepted := 0
    for result := range results { if result { accepted++ } }
    if accepted != 1 { t.Fatalf("expected exactly one ticket use, got %d", accepted) }
}
