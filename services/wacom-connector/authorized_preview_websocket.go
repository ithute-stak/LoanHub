package main

// Authenticated loopback WebSocket preview adapter. This handler is NOT
// installed by the diagnostics-only service. It cannot capture until a
// trusted backend-backed authorizer is wired by the composition root.
import (
 "context"
 "errors"
 "net/http"
 "strings"
 "sync"
 "time"

 "github.com/gorilla/websocket"
)

const previewWebSocketPath="/v1/preview/stream"
const maxWacomWSMessageBytes=4096

// BackendSessionKey is a non-secret UI binding, NOT a credential.
// Scope and field are derived from verified backend state, never the request.
type approvedWacomWebSocketPreview struct {
 Scope previewTicketScope
 Config authorizedPreviewConfig
 SessionKey string
 FieldID string
}
type wacomWebSocketAuthorizer interface {
 AuthorizeWebSocketPreview(ctx context.Context, ticket string) (approvedWacomWebSocketPreview,error)
}
type wsPreviewRequest struct {
 Type string `json:"type"`
 PreviewTicket string `json:"preview_ticket,omitempty"`
 FieldID string `json:"field_id,omitempty"`
}
type wsPreviewFrame struct {
 Type string `json:"type"`
 SessionKey string `json:"session_key"`
 FieldID string `json:"field_id"`
 Strokes [][]previewPoint `json:"strokes,omitempty"`
}

type localWacomWSServer struct {
 Authority wacomWebSocketAuthorizer
 captureGate chan struct{}
}
func newLocalWacomWSServer(authority wacomWebSocketAuthorizer)*localWacomWSServer{
 return &localWacomWSServer{Authority:authority,captureGate:make(chan struct{},1)}
}
func (s *localWacomWSServer) acquire() bool {
 select {case s.captureGate<-struct{}{}:return true;default:return false}
}
func(s *localWacomWSServer) release(){<-s.captureGate}

func validWacomWSRequest(r *http.Request)bool{
 return r.Host=="127.0.0.1:8765" &&
  r.Header.Get("Origin")=="https://loanhub.co.ls" &&
  r.URL.Path==previewWebSocketPath && r.URL.RawQuery=="" &&
  r.Method==http.MethodGet
}

var wacomWSUpgrader=websocket.Upgrader{
 ReadBufferSize:2048, WriteBufferSize:4096,
 CheckOrigin:func(r *http.Request)bool{return validWacomWSRequest(r)},
}

type oneShotPreviewWSSink struct {
 ctx context.Context
 conn *websocket.Conn
 binding approvedWacomWebSocketPreview
 writeMu sync.Mutex
 delivered bool
}

func(s *oneShotPreviewWSSink) write(frame wsPreviewFrame)error{
 if err:=s.ctx.Err();err!=nil{return err}
 s.writeMu.Lock();defer s.writeMu.Unlock()
 if err:=s.conn.SetWriteDeadline(time.Now().Add(2*time.Second));err!=nil{return err}
 return s.conn.WriteJSON(frame)
}
func(s *oneShotPreviewWSSink) DeliverPreview(ctx context.Context, scope previewTicketScope, strokes [][]previewPoint)error{
 if err:=ctx.Err();err!=nil{return err}
 if s.delivered {return errors.New("preview already delivered")}
 // Source is already validated and calibrated by the authorized coordinator.
 // No partial/unverified pen frames may reach the browser.
 if err:=s.write(wsPreviewFrame{Type:"preview_strokes",SessionKey:s.binding.SessionKey,FieldID:s.binding.FieldID,Strokes:strokes});err!=nil{return err}
 s.delivered=true
 return nil
}

func(s *localWacomWSServer) ServeHTTP(w http.ResponseWriter,r *http.Request){
 w.Header().Set("Cache-Control","no-store")
 w.Header().Set("X-Content-Type-Options","nosniff")
 if !validWacomWSRequest(r){http.Error(w,"Forbidden",http.StatusForbidden);return}
 if s==nil||s.Authority==nil {http.Error(w,"Preview disabled",http.StatusServiceUnavailable);return}
 // Reject device contention before authorizing or touching the SDK.
 if !s.acquire(){http.Error(w,"Wacom device busy",http.StatusConflict);return}
 defer s.release()
 conn,err:=wacomWSUpgrader.Upgrade(w,r,nil)
 if err!=nil{return}
 defer conn.Close()
 conn.SetReadLimit(maxWacomWSMessageBytes)
 _=conn.SetReadDeadline(time.Now().Add(3*time.Second))
 var req wsPreviewRequest
 if err:=conn.ReadJSON(&req);err!=nil{return}
 if req.Type!="authorize_preview"||len(req.PreviewTicket)<64||len(req.PreviewTicket)>3500||
  req.FieldID==""||len(req.FieldID)>128||strings.TrimSpace(req.FieldID)!=req.FieldID{return}
 // No client-supplied tenant, hash, session, or workstation scope accepted.
 ctx,cancel:=context.WithTimeout(r.Context(),20*time.Second)
 defer cancel()
 binding,err:=s.Authority.AuthorizeWebSocketPreview(ctx,req.PreviewTicket)
 if err!=nil{return}
 if binding.FieldID!=req.FieldID||binding.SessionKey==""||len(binding.SessionKey)>256{return}
 // Coordinator independently verifies ticket signature/scope and durable
 // one-use replay, enrollment, and active backend revocation state.
 sink:=&oneShotPreviewWSSink{ctx:ctx,conn:conn,binding:binding}
 binding.Config.Sink=sink
 if binding.Config.MaxDuration<=0||binding.Config.MaxDuration>12*time.Second{return}
 // After the first message the only client command accepted is cancellation.
 // This goroutine must never write to the socket; it only cancels SDK work.
 go func(){
  for {
   _=conn.SetReadDeadline(time.Now().Add(15*time.Second))
   var command wsPreviewRequest
   if err:=conn.ReadJSON(&command);err!=nil {cancel();return}
   if command.Type!="cancel"||command.PreviewTicket!=""||command.FieldID!=""{cancel();return}
   cancel();return
  }
 }()
 if err:=sink.write(wsPreviewFrame{Type:"authorized",SessionKey:binding.SessionKey,FieldID:binding.FieldID});err!=nil{return}
 err=runEphemeralAuthorizedPreview(ctx,req.PreviewTicket,binding.Scope,time.Now().UTC(),binding.Config)
 if err!=nil||ctx.Err()!=nil{return}
 _=sink.write(wsPreviewFrame{Type:"complete",SessionKey:binding.SessionKey,FieldID:binding.FieldID})
 // Closing the connection releases the SDK capture lease and reader.
}
