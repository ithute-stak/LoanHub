package main

// Local PC user interface. The browser speaks only to this loopback listener;
// the Go process alone holds the LoanHub access token in memory.
import (
    "context"
    "crypto/rand"
    "crypto/subtle"
    "encoding/hex"
    "errors"
    "html/template"
    "log"
    "net"
    "net/http"
    "strings"
    "sync"
    "time"
)

const (
    pcUIAddr = "127.0.0.1:8767"
    pcUIOrigin = "http://127.0.0.1:8767"
    pcUISessionCookie = "loanhub_pc_session"
    pcSessionTTL = 20 * time.Minute
    pcSessionLimit = 64
)

type pcUISession struct {
    mu sync.Mutex
    csrf string
    expires time.Time
    client *LoanHubPCClient
    status *LoanHubOperatorStatus
    lastClient *LoanHubClientLookup
    feedback string
    capture *pcPendingCapture
    reviewQueue []LoanHubReviewCapture
    documentIntent *LoanHubDocumentIntent
    lastDocumentCaptureID string
}

type pcUI struct {
    origin string
    mu sync.Mutex
    sessions map[string]*pcUISession
    transport *http.Client // optional injected HTTPS transport in tests
    sdkCapture func() (disposableWacomPreview,error)
    workstationKeyDir string // when configured, login requires verified LoanHub workstation proof
    captureMu sync.Mutex
}

type pcUIPage struct {
    CSRF string
    Authenticated bool
    Feedback string
    Status *LoanHubOperatorStatus
    Client *LoanHubClientLookup
    Pending *pcPendingCapture
    CaptureEnabled bool
    ReviewQueue []LoanHubReviewCapture
    DocumentIntent *LoanHubDocumentIntent
    DocumentCaptureID string
}

var pcUITemplate = template.Must(template.New("pc").Parse(`<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="same-origin"><title>LoanHub | Wacom PC</title>
<style>
:root{color-scheme:light;font-family:system-ui,-apple-system,sans-serif;color:#172d43;background:#f0f4f9}
*{box-sizing:border-box}body{margin:0}main{max-width:660px;margin:6vh auto;padding:20px}
header{display:flex;justify-content:space-between;align-items:center;margin-bottom:22px}
.brand{font-weight:800;font-size:22px;color:#153d67}.tag{font-size:12px;padding:6px 12px;background:#e1eafb;border-radius:24px}
.panel{padding:26px;background:white;border-radius:18px;box-shadow:0 6px 30px #102e4812;margin-bottom:16px}
h1{font-size:23px;margin:0 0 8px}h2{font-size:18px;margin:0 0 10px}p{line-height:1.5;color:#52637a}
label{display:block;font-weight:650;font-size:13px;margin:16px 0 6px}
input{width:100%;padding:12px;font-size:15px;border:1px solid #b7c5d4;border-radius:9px}
button{margin-top:18px;padding:12px 18px;border:0;border-radius:9px;background:#164d7d;color:white;font-weight:750;cursor:pointer}
button:focus,input:focus{outline:3px solid #8cc6ff}
.secondary{background:#e9edf4;color:#1a3858}.notice{padding:12px 14px;background:#eaf1fa;border-radius:10px;color:#234b6c}
.warn{background:#fff3d9;color:#765313}.client{padding:12px;border:1px solid #d3e2ee;border-radius:12px}
footer{font-size:13px;color:#66758a;text-align:center}
</style></head><body><main>
<header><div class="brand">LoanHub · Wacom PC</div><div class="tag">Local workstation</div></header>
{{if .Feedback}}<p class="notice" role="status">{{.Feedback}}</p>{{end}}
{{if not .Authenticated}}
<section class="panel"><h1>Operator sign in</h1>
<p>Use your existing LoanHub credentials to access your company's signature desk.</p>
<form method="post" action="/login" autocomplete="off">
<input type="hidden" name="csrf" value="{{.CSRF}}">
<label for="phone">LoanHub phone number</label><input id="phone" name="phone" maxlength="30" required autocomplete="username">
<label for="pass">Password</label><input id="pass" type="password" name="password" maxlength="128" required autocomplete="current-password">
<button type="submit">Sign in securely</button>
</form></section>
{{else}}
<section class="panel"><h1>Operator status</h1>
{{if .Status}}
<p><strong>{{if .Status.FullName}}{{.Status.FullName}}{{else}}Authenticated operator{{end}}</strong></p>
<p>Signature status: <strong>{{.Status.SignatureStatus}}</strong></p>
{{if .Status.RequiresCapture}}<p class="notice warn">Your signature is missing. STU-540 capture will be enabled after SDK integration and review.</p>{{else}}<p class="notice">An existing capture is recorded. Approval for document signing is separate.</p>{{end}}
{{else}}<p>Operator status unavailable. You can refresh below.</p>{{end}}
<form method="post" action="/refresh"><input type="hidden" name="csrf" value="{{.CSRF}}"><button class="secondary">Refresh operator status</button></form>
</section>
<section class="panel"><h2>Find a client</h2>
<p>Search by National ID. Verify the returned name with the person present before collecting any signature.</p>
<form method="post" action="/lookup"><input type="hidden" name="csrf" value="{{.CSRF}}">
<label for="national_id">Client National ID</label><input id="national_id" name="national_id" maxlength="50" required>
<button type="submit">Find client</button></form>
{{if .Client}}
<div class="client"><p>Result: <strong>{{.Client.Status}}</strong></p>
{{if .Client.Client}}
<p>Full name: <strong>{{.Client.Client.FullName}}</strong></p>
<p>Borrower ID: <code>{{.Client.Client.BorrowerID}}</code></p>
<p>Signature: <strong>{{.Client.Client.SignatureStatus}}</strong></p>
{{if .Client.Client.RequiresCapture}}<p class="notice warn">Client signature is required. Physical capture is not yet activated.</p>{{end}}
{{end}}</div>{{end}}
</section>
<section class="panel"><h2>Document-specific evidence</h2>
<p>Review the EXACT contract PDF in LoanHub before requesting borrower consent. This desk collects evidence only; it never signs or changes a loan.</p>
{{if .Client}}{{if .Client.Client}}
<form method="post" action="/document-prepare"><input type="hidden" name="csrf" value="{{.CSRF}}">
<label>Contract ID</label><input name="contract_id" required>
<label>Contract PDF managed file ID</label><input name="source_file_id" required>
<label>Document version (number)</label><input name="document_version" value="1" required>
<button type="submit">Prepare exact document</button></form>{{end}}{{end}}
{{if .DocumentIntent}}
<p>Document SHA-256: <code>{{.DocumentIntent.DocumentSHA256}}</code></p>
<p>State: {{.DocumentIntent.Status}} (not signed)</p>
{{if eq .DocumentIntent.Status "prepared"}}
<form method="post" action="/document-consent">
<input type="hidden" name="csrf" value="{{.CSRF}}">
<input type="hidden" name="displayed_sha256" value="{{.DocumentIntent.DocumentSHA256}}">
<label>Consent evidence reference</label><input name="document_consent_reference" minlength="4" required>
<label><input type="checkbox" name="signer_confirmed" value="yes" required style="width:auto"> Borrower has reviewed this exact document and explicitly confirmed consent</label>
<button type="submit">Record exact-document consent evidence</button></form>{{end}}
{{if .DocumentCaptureID}}<form method="post" action="/document-attach">
<input type="hidden" name="csrf" value="{{.CSRF}}">
<button type="submit">Link captured handwriting evidence to this document</button></form>{{end}}
{{end}}</section>
<section class="panel"><h2>Signature capture</h2>

{{if not .CaptureEnabled}}
<p class="notice warn">Physical capture disabled until the official STU-540 SDK has been configured and verified on this PC.</p>
{{else}}
{{if .Pending}}
<p>Review handwriting for: <strong>{{.Pending.Label}}</strong></p>
<img src="/preview" alt="Handwriting captured on local Wacom pad" style="width:100%;height:auto;border:1px solid #ccd7e1">
<form method="post" action="/upload">
<input type="hidden" name="csrf" value="{{.CSRF}}">
<label><input type="checkbox" name="approved" value="yes" required style="width:auto"> I have checked the captured handwriting with the signer and confirmed consent to submit it for review.</label>
<button type="submit">Upload to LoanHub for review</button></form>
<form method="post" action="/discard"><input type="hidden" name="csrf" value="{{.CSRF}}"><button class="secondary" type="submit">Discard handwriting</button></form>
{{else}}
<p>The signer must be present and consent to capture. This is not contract signing.</p>
<form method="post" action="/capture">
<input type="hidden" name="csrf" value="{{.CSRF}}">
<label for="signer_kind">Signer</label>
<select id="signer_kind" name="signer_kind" required>
<option value="operator">Logged-in operator</option>
{{if .Client}}{{if .Client.Client}}{{if .Client.Client.RequiresCapture}}<option value="client">Located client: {{.Client.Client.FullName}}</option>{{end}}{{end}}{{end}}
</select>
<label for="confirm_name">Type the signer's full name to confirm</label>
<input id="confirm_name" name="confirm_name" maxlength="200" required>
<label for="consent_reference">Consent record reference</label>
<input id="consent_reference" name="consent_reference" minlength="4" maxlength="180" required>
<label><input type="checkbox" name="consent" value="yes" style="width:auto" required> Identity confirmed, signer present and consent obtained.</label>
<button type="submit">Capture handwriting on STU-540</button>
</form>{{end}}
{{end}}

<section class="panel"><h2>Independent evidence review</h2>
<p>Company management only. The reviewer must be different from the capturing operator. Reviewing evidence does not sign any document.</p>
<form method="post" action="/review-refresh"><input type="hidden" name="csrf" value="{{.CSRF}}"><button class="secondary" type="submit">Load pending evidence</button></form>
{{range .ReviewQueue}}
<div class="client">
<p><strong>{{.SignerKind}}</strong> capture · <code>{{.CaptureFileID}}</code></p>
<p>Signer ID: <code>{{.SignerID}}</code>{{if .CapturedByUserID}} · Captured by: <code>{{.CapturedByUserID}}</code>{{end}}</p>
<p>Scan: {{.ScanStatus}} · {{.EvidenceStatus}}</p>
<img src="/review-preview/{{.CaptureFileID}}" alt="Independent review of handwriting evidence" style="width:100%;height:auto;border:1px solid #ccd7e1">
<form method="post" action="/review-decision">
<input type="hidden" name="csrf" value="{{$.CSRF}}">
<input type="hidden" name="file_id" value="{{.CaptureFileID}}">
<label>Decision</label><select name="decision" required>
<option value="reject">Reject evidence</option>
<option value="verify">Verify evidence only (not signing permission)</option>
</select>
<label>Evidence reference</label><input name="evidence_reference" minlength="4" maxlength="160" required>
<label>Reason</label><input name="reason" minlength="8" maxlength="400" required>
<label><input type="checkbox" name="identity_checked" value="yes" style="width:auto"> I independently checked signer identity</label>
<label><input type="checkbox" name="consent_checked" value="yes" style="width:auto"> I independently checked evidence consent</label>
<button type="submit">Record evidence review decision</button>
</form></div>{{end}}
</section>
<form method="post" action="/switch-operator"><input type="hidden" name="csrf" value="{{.CSRF}}"><button class="secondary" type="submit">Switch operator (sign out securely)</button></form>
<form method="post" action="/logout"><input type="hidden" name="csrf" value="{{.CSRF}}"><button class="secondary" type="submit">Sign out</button></form>
</section>
{{end}}
<footer>Runs only on this PC · Handwriting stays in memory until submitted or discarded · No automatic contract signing</footer>
</main></body></html>`))

func pcToken() (string, error) {
    var b [32]byte
    if _, err := rand.Read(b[:]); err != nil { return "", err }
    return hex.EncodeToString(b[:]), nil
}

func newPCUI(origin string) (*pcUI, error) {
    if _, err := NewLoanHubPCClient(origin, nil); err != nil { return nil, err }
    return &pcUI{origin:origin, sessions:make(map[string]*pcUISession)}, nil
}

func (ui *pcUI) getSession(w http.ResponseWriter, r *http.Request) (*pcUISession, bool) {
    ui.mu.Lock()
    defer ui.mu.Unlock()
    now := time.Now()
    for key, session := range ui.sessions {
        if now.After(session.expires) {
            session.mu.Lock()
            session.discardCapture()
            if session.client!=nil {session.client.Logout()}
            session.reviewQueue=nil
            session.mu.Unlock()
            delete(ui.sessions,key)
        }
    }
    if cookie, err := r.Cookie(pcUISessionCookie); err == nil {
        if session, ok := ui.sessions[cookie.Value]; ok {
            session.expires = now.Add(pcSessionTTL)
            return session, true
        }
    }
    if r.Method != http.MethodGet || len(ui.sessions) >= pcSessionLimit {
        return nil, false
    }
    id, err := pcToken()
    if err != nil { return nil, false }
    csrf, err := pcToken()
    if err != nil { return nil, false }
    session := &pcUISession{csrf:csrf, expires:now.Add(pcSessionTTL)}
    ui.sessions[id] = session
    http.SetCookie(w, &http.Cookie{
        Name:pcUISessionCookie, Value:id, Path:"/", HttpOnly:true,
        SameSite:http.SameSiteStrictMode, MaxAge:int(pcSessionTTL.Seconds()),
    })
    return session, true
}

func (ui *pcUI) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Cache-Control", "no-store")
    w.Header().Set("X-Content-Type-Options", "nosniff")
    w.Header().Set("X-Frame-Options", "DENY")
    w.Header().Set("Content-Security-Policy", "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
    w.Header().Set("Referrer-Policy", "same-origin")
    if r.Host != pcUIAddr || r.URL.RawQuery != "" {
        http.Error(w,"Forbidden",http.StatusForbidden)
        return
    }
    if r.Method != http.MethodGet && r.Method != http.MethodPost {
        http.Error(w,"Method not allowed",http.StatusMethodNotAllowed)
        return
    }
    if r.Method == http.MethodPost && r.Header.Get("Origin") != pcUIOrigin {
        http.Error(w,"Forbidden",http.StatusForbidden)
        return
    }
    reviewPreview := strings.HasPrefix(r.URL.Path,"/review-preview/")
    if r.URL.Path != "/" && r.URL.Path != "/login" && r.URL.Path != "/lookup" &&
        r.URL.Path != "/refresh" && r.URL.Path != "/logout" &&
        r.URL.Path != "/switch-operator" &&
        r.URL.Path != "/document-prepare" && r.URL.Path != "/document-consent" &&
        r.URL.Path != "/document-attach" &&
        r.URL.Path != "/capture" && r.URL.Path != "/upload" &&
        r.URL.Path != "/discard" && r.URL.Path != "/preview" &&
        r.URL.Path != "/review-refresh" && r.URL.Path != "/review-decision" &&
        !reviewPreview {
        http.NotFound(w,r)
        return
    }
    if r.Method == http.MethodGet && r.URL.Path != "/" && r.URL.Path != "/preview" && !reviewPreview {
        http.NotFound(w,r)
        return
    }
    session, ok := ui.getSession(w,r)
    if !ok { http.Error(w,"Session unavailable; reload the page",http.StatusForbidden); return }
    session.mu.Lock()
    defer session.mu.Unlock()
    if r.Method == http.MethodPost {
        r.Body = http.MaxBytesReader(w,r.Body,4096)
        if err := r.ParseForm(); err != nil ||
            subtle.ConstantTimeCompare([]byte(r.PostForm.Get("csrf")),[]byte(session.csrf)) != 1 {
            http.Error(w,"Invalid form submission",http.StatusForbidden)
            return
        }
    }
    if reviewPreview {
        if r.Method != http.MethodGet {http.Error(w,"Method not allowed",http.StatusMethodNotAllowed);return}
        ctx,cancel:=context.WithTimeout(r.Context(),15*time.Second)
        defer cancel()
        ui.serveReviewPreview(ctx,w,session,strings.TrimPrefix(r.URL.Path,"/review-preview/"))
        return
    }
    if r.URL.Path == "/preview" {
        if r.Method != http.MethodGet || session.client == nil || session.capture == nil {
            http.NotFound(w,r); return
        }
        if time.Now().After(session.capture.expires) {
            session.discardCapture()
            http.NotFound(w,r); return
        }
        w.Header().Set("Content-Type","image/png")
        w.Header().Set("Content-Disposition","inline; filename=capture-preview.png")
        _,_ = w.Write(session.capture.preview.PNG)
        return
    }
    session.feedback = ""
    if r.Method == http.MethodPost {
        ctx,cancel := context.WithTimeout(r.Context(),15*time.Second)
        defer cancel()
        switch r.URL.Path {
        case "/login":
            if session.client != nil { session.feedback="Already signed in"; break }
            client,err := NewLoanHubPCClient(ui.origin,ui.transport)
            if err != nil { session.feedback="LoanHub origin configuration unavailable"; break }
            err=client.Login(ctx,strings.TrimSpace(r.PostForm.Get("phone")),
                r.PostForm.Get("password"),"", "")
            if err != nil { session.feedback="Login failed. Check credentials or account requirements. Multi-company accounts require company selection."; break }
            if ui.workstationKeyDir != "" {
                client.workstationKeyDir=ui.workstationKeyDir
                if err := client.VerifyLocalWorkstation(ctx,ui.workstationKeyDir); err != nil {
                    client.Logout()
                    session.feedback="Access denied: this employee or workstation could not be verified by LoanHub."
                    break
                }
            }
            session.client=client
            status,err := client.OperatorSignatureStatus(ctx)
            if err == nil { session.status=&status } else {
                client.Logout()
                session.client=nil
                session.status=nil
                session.feedback="Access denied: operator permission or company status could not be verified."
            }
        case "/document-prepare":
            ui.documentPrepareRequest(ctx,r,session)
        case "/document-consent":
            ui.documentConsentRequest(ctx,r,session)
        case "/document-attach":
            ui.documentAttachRequest(ctx,session)
        case "/refresh":
            if session.client == nil { session.feedback="Sign in first"; break }
            status,err := session.client.OperatorSignatureStatus(ctx)
            if err != nil { session.feedback="Could not refresh signature status." } else { session.status=&status }
        case "/lookup":
            session.discardCapture()
            session.lastClient=nil
            if session.client == nil { session.feedback="Sign in first"; break }
            result,err := session.client.FindClient(ctx,strings.TrimSpace(r.PostForm.Get("national_id")))
            if err != nil { session.feedback="Client lookup unavailable or not authorized." } else { session.lastClient=&result }
        case "/capture":
            ui.captureRequest(r,session)
        case "/upload":
            ui.uploadRequest(ctx,r,session)
        case "/discard":
            session.discardCapture()
            session.feedback="Capture discarded"
        case "/review-refresh":
            ui.refreshReviewQueue(ctx,session)
        case "/review-decision":
            ui.decideReview(ctx,r,session)
        case "/logout", "/switch-operator":
            session.discardCapture()
            revokeFailed := false
            if session.client != nil {
                if err := session.client.RevokeBridgeSession(ctx); err != nil { revokeFailed = true }
                session.client.Logout()
            }
            session.client=nil
            session.status=nil
            session.lastClient=nil
            session.reviewQueue=nil
            session.forgetDocument()
            if r.URL.Path == "/switch-operator" {
                session.feedback="Previous operator signed out. Next operator must sign in with their own LoanHub credentials."
            } else { session.feedback="Signed out" }
            if revokeFailed { session.feedback += " Server session revocation could not be confirmed; credential expires automatically within five minutes." }
        default:
            http.NotFound(w,r); return
        }
    }
    w.Header().Set("Content-Type","text/html; charset=utf-8")
    if err := pcUITemplate.Execute(w,pcUIPage{
        CSRF:session.csrf, Authenticated:session.client != nil,
        Feedback:session.feedback, Status:session.status, Client:session.lastClient,
        Pending:session.capture, CaptureEnabled:ui.sdkCapture!=nil,
        ReviewQueue:session.reviewQueue,
        DocumentIntent:session.documentIntent, DocumentCaptureID:session.lastDocumentCaptureID,
    }); err != nil {
        log.Println("Wacom PC UI template rendering failed")
    }
}

func servePCUI(origin string, capture func() (disposableWacomPreview,error)) error {
    return servePCUIWithIdentity(origin,capture,"")
}

func servePCUIWithIdentity(origin string, capture func() (disposableWacomPreview,error), workstationKeyDir string) error {
    ui,err := newPCUI(origin)
    if err != nil { return err }
    ui.sdkCapture=capture
    ui.workstationKeyDir=workstationKeyDir
    listener,err := net.Listen("tcp4",pcUIAddr)
    if err != nil { return err }
    defer listener.Close()
    server:=&http.Server{
        Handler:ui,ReadHeaderTimeout:3*time.Second,
        ReadTimeout:45*time.Second,WriteTimeout:45*time.Second,
        IdleTimeout:30*time.Second,MaxHeaderBytes:8192,
    }
    log.Printf("LoanHub Wacom PC UI available at %s; capture enabled: %t",pcUIOrigin,ui.sdkCapture!=nil)
    err=server.Serve(listener)
    if errors.Is(err,http.ErrServerClosed) { return nil }
    return err
}
