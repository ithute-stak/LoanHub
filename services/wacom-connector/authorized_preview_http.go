package main

// Preview HTTP adapter. Intentionally NOT installed in diagnostics mode.
// A production caller must provide a backend-backed, enrolled-workstation
// authority; no request fields may supply a trusted preview scope.
import (
 "context"
 "encoding/json"
 "errors"
 "io"
 "net/http"
 "strings"
 "time"
)

const previewPath = "/v1/preview/capture"

type previewCaptureAuthorizer interface {
 // Must derive scope from an independently authenticated live backend session
 // and enrolled workstation (never from browser-submitted IDs).
 // Must return pinned signing keys, durable ticket replay protection,
 // live revocation checks, actual SDK calibration and an approved SDK source.
 AuthorizeCapture(context.Context, string) (previewTicketScope, authorizedPreviewConfig, error)
}

type previewCaptureRequest struct {
 Ticket string `json:"preview_ticket"`
}
type previewCaptureResponse struct {
 Purpose string `json:"purpose"`
 Strokes [][]previewPoint `json:"strokes"`
}

type memoryPreviewSink struct { strokes [][]previewPoint; delivered bool }
func (s *memoryPreviewSink) DeliverPreview(ctx context.Context, _ previewTicketScope, strokes [][]previewPoint) error {
 if err:=ctx.Err();err!=nil{return err}
 if s.delivered {return errors.New("preview already delivered")}
 s.strokes=strokes
 s.delivered=true
 return nil
}

// newAuthorizedPreviewHTTPHandler is deliberately dependency-injected.
// Diagnostics must continue using its existing status-only handler.
func newAuthorizedPreviewHTTPHandler(authorizer previewCaptureAuthorizer) http.Handler {
 return http.HandlerFunc(func(w http.ResponseWriter,r *http.Request) {
  w.Header().Set("Cache-Control","no-store")
  w.Header().Set("Pragma","no-cache")
  w.Header().Set("X-Content-Type-Options","nosniff")
  w.Header().Set("Referrer-Policy","no-referrer")
  if r.URL.Path != previewPath {http.NotFound(w,r);return}
  // Origin is required, including for native callers, to avoid accidentally
  // admitting cross-origin web requests or command-line bypasses.
  if r.Host != "127.0.0.1:8765" || r.Header.Get("Origin")!="https://loanhub.co.ls" {
   http.Error(w,"Forbidden",http.StatusForbidden);return
  }
  w.Header().Set("Access-Control-Allow-Origin","https://loanhub.co.ls")
  w.Header().Set("Vary","Origin")
  if r.Method==http.MethodOptions {
   w.Header().Set("Access-Control-Allow-Methods","POST")
   w.Header().Set("Access-Control-Allow-Headers","Content-Type")
   w.Header().Set("Access-Control-Max-Age","0")
   w.WriteHeader(http.StatusNoContent)
   return
  }
  if r.Method!=http.MethodPost {w.Header().Set("Allow","POST, OPTIONS");http.Error(w,"Method not allowed",405);return}
  if authorizer==nil {http.Error(w,"Preview disabled",http.StatusServiceUnavailable);return}
  if !strings.EqualFold(strings.TrimSpace(strings.Split(r.Header.Get("Content-Type"),";")[0]),"application/json") {
   http.Error(w,"Expected JSON",http.StatusUnsupportedMediaType);return
  }
  r.Body=http.MaxBytesReader(w,r.Body,4096)
  var request previewCaptureRequest
  decoder:=json.NewDecoder(r.Body)
  decoder.DisallowUnknownFields()
  if err:=decoder.Decode(&request);err!=nil {http.Error(w,"Invalid preview request",400);return}
  var extra any
  if err:=decoder.Decode(&extra);err!=io.EOF {http.Error(w,"Invalid preview request",400);return}
  if len(request.Ticket)<64 || len(request.Ticket)>3500 {
   http.Error(w,"Invalid preview ticket",400);return
  }
  scope, config, err:=authorizer.AuthorizeCapture(r.Context(),request.Ticket)
  if err!=nil {http.Error(w,"Preview authorization denied",http.StatusForbidden);return}
  sink:=&memoryPreviewSink{}
  defer func(){for i:=range sink.strokes {clear(sink.strokes[i]);sink.strokes[i]=nil};sink.strokes=nil}()
  // Never trust a sink passed by the caller to send to a different browser.
  config.Sink=sink
  if err:=runEphemeralAuthorizedPreview(r.Context(),request.Ticket,scope,time.Now().UTC(),config);err!=nil {
   http.Error(w,"Preview unavailable or revoked",http.StatusForbidden);return
  }
  if !sink.delivered {http.Error(w,"No preview available",http.StatusConflict);return}
  w.Header().Set("Content-Type","application/json")
  _=json.NewEncoder(w).Encode(previewCaptureResponse{Purpose:"test-preview-only",Strokes:sink.strokes})
 })
}
