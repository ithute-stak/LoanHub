package main

// Local, explicit workstation identity provisioning. Never reachable over
// the diagnostic HTTP listener. The private Ed25519 seed remains on disk
// in a privately owned folder; only a public registration JSON is printed.
import (
    "crypto/ed25519"
    "crypto/rand"
    "encoding/base64"
    "encoding/hex"
    "encoding/json"
    "errors"
    "fmt"
    "io"
    "os"
    "path/filepath"
    "syscall"
)

const workstationIdentityFilename = "workstation-identity.json"
const workstationIdentityMaxBytes = 2048

type workstationIdentityFile struct {
    Version int `json:"version"`
    WorkstationID string `json:"workstation_id"`
    PrivateSeedBase64 string `json:"private_seed_base64"`
}

type workstationPublicRegistration struct {
    WorkstationID string `json:"workstation_id"`
    PublicKeyBase64 string `json:"ed25519_public_key_base64"`
}

// This uses a strict existing directory to avoid creating secrets under
// temporary/untrusted paths. Parent path ownership is an OS provisioning
// requirement and should be reviewed before deployment.
func requirePrivateWorkstationDirectory(directory string) error {
    if !filepath.IsAbs(directory) || filepath.Clean(directory) != directory {
        return errors.New("workstation key directory must be absolute and clean")
    }
    info, err := os.Lstat(directory)
    if err != nil { return fmt.Errorf("workstation key directory unavailable: %w", err) }
    raw, ok := info.Sys().(*syscall.Stat_t)
    if info.Mode()&os.ModeSymlink != 0 || !info.IsDir() || info.Mode().Perm() != 0700 ||
        !ok || raw.Uid != uint32(os.Geteuid()) {
        return errors.New("workstation key directory must be owned, private and non-symlink (0700)")
    }
    return nil
}

func generateWorkstationUUID() (string, error) {
    raw := make([]byte,16)
    if _, err := io.ReadFull(rand.Reader, raw); err != nil { return "", err }
    raw[6] = (raw[6]&0x0f)|0x40
    raw[8] = (raw[8]&0x3f)|0x80
    h:=hex.EncodeToString(raw)
    return fmt.Sprintf("%s-%s-%s-%s-%s",h[:8],h[8:12],h[12:16],h[16:20],h[20:]),nil
}

// initializeWorkstationIdentity writes the secret exactly once. If the path
// already exists or any step fails, the command never emits a registration
// request; it never prints the private seed. A partially written file must
// be handled manually, not overwritten by retry.
func initializeWorkstationIdentity(directory string) (workstationPublicRegistration,error) {
    if err := requirePrivateWorkstationDirectory(directory); err != nil { return workstationPublicRegistration{},err }
    uuid, err := generateWorkstationUUID()
    if err != nil { return workstationPublicRegistration{},err }
    public, private, err := ed25519.GenerateKey(rand.Reader)
    if err != nil { return workstationPublicRegistration{},err }
    data := workstationIdentityFile{
        Version:1, WorkstationID:uuid,
        PrivateSeedBase64:base64.StdEncoding.EncodeToString(private.Seed()),
    }
    raw,err:=json.Marshal(data)
    if err!=nil {return workstationPublicRegistration{},err}
    path := filepath.Join(directory, workstationIdentityFilename)
    // O_EXCL avoids accidentally resetting an already enrolled device.
    f,err:=os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL|syscall.O_NOFOLLOW,0600)
    if err!=nil {return workstationPublicRegistration{},fmt.Errorf("workstation identity already exists or cannot be created: %w",err)}
    _,writeErr:=f.Write(raw)
    syncErr:=f.Sync()
    closeErr:=f.Close()
    if writeErr!=nil||syncErr!=nil||closeErr!=nil {
        return workstationPublicRegistration{},errors.New("workstation identity could not be durably written; inspect file before retry")
    }
    dir,err:=os.Open(directory)
    if err!=nil {return workstationPublicRegistration{},errors.New("workstation identity directory cannot be synced")}
    syncErr=dir.Sync()
    closeErr=dir.Close()
    if syncErr!=nil||closeErr!=nil {return workstationPublicRegistration{},errors.New("workstation identity directory sync failed")}
    return workstationPublicRegistration{
        WorkstationID:uuid,PublicKeyBase64:base64.StdEncoding.EncodeToString(public),
    },nil
}

// loadWorkstationIdentity is a local-only building block for a future
// challenge-response client. Caller must keep key material in memory only,
// never return it from diagnostic routes or logs.
func loadWorkstationIdentity(directory string) (string,ed25519.PrivateKey,error) {
    if err:=requirePrivateWorkstationDirectory(directory);err!=nil {return "",nil,err}
    path:=filepath.Join(directory,workstationIdentityFilename)
    info,err:=os.Lstat(path)
    if err!=nil {return "",nil,err}
    stat,ok:=info.Sys().(*syscall.Stat_t)
    if !info.Mode().IsRegular()||info.Mode().Perm()!=0600||!ok||stat.Uid!=uint32(os.Geteuid())||
        info.Size()<=0||info.Size()>workstationIdentityMaxBytes {
        return "",nil,errors.New("untrusted workstation identity file")
    }
    f,err:=os.OpenFile(path,os.O_RDONLY|syscall.O_NOFOLLOW,0)
    if err!=nil {return "",nil,err}
    defer f.Close()
    opened,err:=f.Stat()
    if err!=nil||!opened.Mode().IsRegular()||opened.Mode().Perm()!=0600||!os.SameFile(info,opened) {
        return "",nil,errors.New("workstation identity changed during read")
    }
    dec:=json.NewDecoder(io.LimitReader(f,workstationIdentityMaxBytes+1))
    dec.DisallowUnknownFields()
    var ident workstationIdentityFile
    if err:=dec.Decode(&ident);err!=nil {return "",nil,err}
    if err:=dec.Decode(new(any));err!=io.EOF{return "",nil,errors.New("trailing workstation identity data")}
    if ident.Version!=1||!validUUID(ident.WorkstationID) {return "",nil,errors.New("invalid workstation identity")}
    seed,err:=base64.StdEncoding.Strict().DecodeString(ident.PrivateSeedBase64)
    if err!=nil||len(seed)!=ed25519.SeedSize {return "",nil,errors.New("invalid workstation private seed")}
    return ident.WorkstationID,ed25519.NewKeyFromSeed(seed),nil
}
