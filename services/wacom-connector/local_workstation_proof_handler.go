package main

// Optional, strictly scoped local preview proof exchange. NOT mounted by
// the diagnostics server. The browser sends only a *backend-signed*
// challenge; no arbitrary message signing or key export is exposed.
import (
 "bytes"
 "crypto/ed25519"
 "encoding/json"
 "io"
 "net/http"
 "strings"
 "sync"
 "time"
)

const localWacomChallengeProofPath="/v1/preview/workstation-proof"

type localWacomChallengeProofHandler struct {
 IdentityDirectory string
 TrustedBackendKeys map[string]ed25519.PublicKey
 mu sync.Mutex
 lastAttempt time.Time
}

func(h *localWacomChallengeProofHandler) ServeHTTP(w http.ResponseWriter,r *http.Request){
 w.Header().Set("Cache-Control","no-store")
 w.Header().Set("X-Content-Type-Options","nosniff")
 if h==nil||h.IdentityDirectory==""||len(h.TrustedBackendKeys)==0 {
  http.Error(w,"Unavailable",http.StatusServiceUnavailable);return
 }
 if r.URL.Path!=localWacomChallengeProofPath||
  r.URL.RawQuery!=""||r.Host!="127.0.0.1:8765"||
  r.Header.Get("Origin")!="https://loanhub.co.ls"||
  r.Header.Get("Cookie")!=""||r.Header.Get("Authorization")!="" {
  http.Error(w,"Forbidden",http.StatusForbidden);return
 }
 w.Header().Set("Access-Control-Allow-Origin","https://loanhub.co.ls")
 w.Header().Set("Vary","Origin")
 if r.Method==http.MethodOptions {
  if r.Header.Get("Access-Control-Request-Method")!="POST" ||
   r.Header.Get("Access-Control-Request-Headers")!="content-type" {
   http.Error(w,"Forbidden",http.StatusForbidden);return
  }
  w.Header().Set("Access-Control-Allow-Methods","POST")
  w.Header().Set("Access-Control-Allow-Headers","Content-Type")
  w.Header().Set("Access-Control-Max-Age","0")
  w.WriteHeader(http.StatusNoContent);return
 }
 if r.Method!=http.MethodPost||!strings.EqualFold(strings.TrimSpace(r.Header.Get("Content-Type")),"application/json") {
  http.Error(w,"Forbidden",http.StatusForbidden);return
 }
 h.mu.Lock()
 if time.Since(h.lastAttempt)<500*time.Millisecond {
  h.mu.Unlock()
  http.Error(w,"Rate limited",http.StatusTooManyRequests);return
 }
 h.lastAttempt=time.Now()
 h.mu.Unlock()
 raw,err:=io.ReadAll(http.MaxBytesReader(w,r.Body,maxWacomChallengeJSON))
 if err!=nil||len(raw)==0 {http.Error(w,"Invalid challenge",http.StatusBadRequest);return}
 // The independently signed envelope authenticates the session ID; it
 // cannot be replaced by an unauthenticated browser selection.
 var incoming backendWorkstationChallenge
 decoder:=json.NewDecoder(bytes.NewReader(raw))
 decoder.DisallowUnknownFields()
 if decoder.Decode(&incoming)!=nil{
  http.Error(w,"Invalid challenge",http.StatusBadRequest);return
 }
 var tail any
 if decoder.Decode(&tail)!=io.EOF||!validUUID(incoming.SessionID){
  http.Error(w,"Invalid challenge",http.StatusBadRequest);return
 }
 proof,err:=signBackendWacomChallenge(
  h.IdentityDirectory,incoming.SessionID,bytes.NewReader(raw),
  time.Now().UTC(),h.TrustedBackendKeys,
 )
 if err!=nil{http.Error(w,"Challenge refused",http.StatusForbidden);return}
 w.Header().Set("Content-Type","application/json")
 _=json.NewEncoder(w).Encode(proof)
}
