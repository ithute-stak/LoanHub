package main

// Socket-level regression tests: exercise the real websocket upgrade and
// first-frame protocol, not only direct HTTP handler calls. These tests
// use no USB, SDK executable, production ticket or legal signing route.
import (
 "context"
 "errors"
 "net/http"
 "net/http/httptest"
 "strings"
 "sync"
 "testing"
 "time"

 "github.com/gorilla/websocket"
)

type observedWacomWSDenial struct {
 mu sync.Mutex
 count int
}
func (a *observedWacomWSDenial) AuthorizeWebSocketPreview(_ context.Context,_ string)(approvedWacomWebSocketPreview,error){
 a.mu.Lock()
 a.count++
 a.mu.Unlock()
 return approvedWacomWebSocketPreview{},errors.New("not authorized")
}
func (a *observedWacomWSDenial) called() int {
 a.mu.Lock();defer a.mu.Unlock()
 return a.count
}

func dialWacomTestSocket(t *testing.T,server *httptest.Server,origin string)(*websocket.Conn,*http.Response,error){
 t.Helper()
 endpoint:="ws"+strings.TrimPrefix(server.URL,"http")+previewWebSocketPath
 // Dial the local test server address while preserving the pinned Host
 // required by the production handler.
 headers:=http.Header{}
 headers.Set("Origin",origin)
 headers.Set("Host","127.0.0.1:8765")
 dialer:=websocket.Dialer{HandshakeTimeout:2*time.Second}
 return dialer.Dial(endpoint,headers)
}

func TestWacomWebSocketRealHandshakeRejectsForeignOrigin(t *testing.T){
 authority:=&observedWacomWSDenial{}
 server:=httptest.NewServer(newLocalWacomWSServer(authority))
 defer server.Close()
 conn,resp,err:=dialWacomTestSocket(t,server,"https://attacker.example")
 if conn!=nil {conn.Close();t.Fatal("untrusted browser upgraded")}
 if err==nil||resp==nil||resp.StatusCode!=http.StatusForbidden {
  t.Fatalf("foreign origin not rejected before upgrade: response=%v error=%v",resp,err)
 }
 if authority.called()!=0 {t.Fatal("origin bypass reached backend authority")}
}

func TestWacomWebSocketRealHandshakeRejectsMissingFirstFrameTicket(t *testing.T){
 authority:=&observedWacomWSDenial{}
 server:=httptest.NewServer(newLocalWacomWSServer(authority))
 defer server.Close()
 conn,_,err:=dialWacomTestSocket(t,server,"https://loanhub.co.ls")
 if err!=nil{t.Fatal(err)}
 defer conn.Close()
 if err:=conn.SetReadDeadline(time.Now().Add(3*time.Second));err!=nil{t.Fatal(err)}
 if err:=conn.WriteJSON(map[string]any{
  "type":"authorize_preview","preview_ticket":"","field_id":"borrower_signature",
 });err!=nil{t.Fatal(err)}
 var response any
 if err:=conn.ReadJSON(&response);err==nil {
  t.Fatalf("connection transmitted data without backend authority: %v",response)
 }
 if authority.called()!=0 {t.Fatal("missing token reached authorizer")}
}

func TestWacomWebSocketRealHandshakeBackendDenialReturnsNoStrokes(t *testing.T){
 authority:=&observedWacomWSDenial{}
 server:=httptest.NewServer(newLocalWacomWSServer(authority))
 defer server.Close()
 conn,_,err:=dialWacomTestSocket(t,server,"https://loanhub.co.ls")
 if err!=nil{t.Fatal(err)}
 defer conn.Close()
 if err:=conn.SetReadDeadline(time.Now().Add(3*time.Second));err!=nil{t.Fatal(err)}
 // A synthetic token only exercises the backend rejection path; it is
 // deliberately never accepted or used to start SDK capture.
 if err:=conn.WriteJSON(map[string]any{
  "type":"authorize_preview",
  "preview_ticket":strings.Repeat("a",128),
  "field_id":"borrower_signature",
 });err!=nil{t.Fatal(err)}
 var frame any
 if err:=conn.ReadJSON(&frame);err==nil{
  t.Fatalf("unauthorized preview frame delivered: %v",frame)
 }
 if authority.called()!=1{t.Fatalf("backend authorization should run once; got %d",authority.called())}
}
