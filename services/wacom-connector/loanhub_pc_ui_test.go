package main

import (
    "net/http"
    "net/http/httptest"
    "net/url"
    "os"
    "path/filepath"
    "regexp"
    "strings"
    "testing"
)

var testCSRF = regexp.MustCompile(`name="csrf" value="([a-f0-9]{64})"`)

func localUIGet(t *testing.T, ui *pcUI) (*http.Cookie, string, string) {
    t.Helper()
    req:=httptest.NewRequest(http.MethodGet,pcUIOrigin+"/",nil)
    recorder:=httptest.NewRecorder()
    ui.ServeHTTP(recorder,req)
    if recorder.Code!=200 { t.Fatalf("GET UI status %d",recorder.Code) }
    cookies:=recorder.Result().Cookies()
    if len(cookies)!=1 || !cookies[0].HttpOnly ||
        cookies[0].SameSite!=http.SameSiteStrictMode { t.Fatal("missing private session cookie") }
    output:=recorder.Body.String()
    found:=testCSRF.FindStringSubmatch(output)
    if len(found)!=2 { t.Fatal("CSRF token missing from local form") }
    if !strings.Contains(output,"Operator sign in") { t.Fatal("login screen missing") }
    return cookies[0],found[1],output
}

func localUIPost(ui *pcUI, cookie *http.Cookie, path string, values url.Values, origin string) *httptest.ResponseRecorder {
    req:=httptest.NewRequest(http.MethodPost,pcUIOrigin+path,strings.NewReader(values.Encode()))
    req.Header.Set("Content-Type","application/x-www-form-urlencoded")
    if origin!="" { req.Header.Set("Origin",origin) }
    req.AddCookie(cookie)
    recorder:=httptest.NewRecorder()
    ui.ServeHTTP(recorder,req)
    return recorder
}

func TestPCUIRequiresLoopbackHostAndCSRF(t *testing.T) {
    ui,err:=newPCUI("https://loanhub.example")
    if err!=nil { t.Fatal(err) }
    cookie,csrf,_:=localUIGet(t,ui)
    payload:=url.Values{"csrf":{csrf},"phone":{"59000000"}}
    for _,origin:=range []string{"","https://attacker.example"} {
        response:=localUIPost(ui,cookie,"/login",payload,origin)
        if response.Code!=403 { t.Fatalf("accepted foreign origin %q: %d",origin,response.Code) }
    }
    response:=localUIPost(ui,cookie,"/login",url.Values{"csrf":{"wrong"}} ,pcUIOrigin)
    if response.Code!=403 { t.Fatal("accepted wrong CSRF") }

    req:=httptest.NewRequest(http.MethodGet,"http://attacker.example/",nil)
    response=httptest.NewRecorder()
    ui.ServeHTTP(response,req)
    if response.Code!=403 { t.Fatal("accepted DNS rebinding Host") }
    if response.Header().Get("Cache-Control")!="no-store" { t.Fatal("cache header missing") }

    req=httptest.NewRequest(http.MethodGet,pcUIOrigin+"/capture",nil)
    response=httptest.NewRecorder()
    ui.ServeHTTP(response,req)
    if response.Code!=404 { t.Fatal("unexpected capture route") }
}

func TestPCUIHTTPSLoginAndClientLookup(t *testing.T) {
    companyID:="4236a21f-5164-48aa-90f3-a35eccd23ae2"
    calls:=0
    api:=httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter,r *http.Request) {
        calls++
        w.Header().Set("Content-Type","application/json")
        switch r.URL.Path {
        case "/api/v1/auth/login":
            _,_=w.Write([]byte(`{"access_token":"synthetic","token_type":"bearer","user":{"is_active":true,"id":"operator","memberships":[{"company_id":"`+companyID+`","is_active":true}]}}`))
        case "/api/v1/local-signatures/me/status":
            if r.Header.Get("Authorization")!="Bearer synthetic" || r.Header.Get("X-Company-ID")!=companyID {
                t.Error("missing operator auth headers")
            }
            _,_=w.Write([]byte(`{"operator_id":"operator","company_id":"`+companyID+`","signature_status":"missing","requires_capture":true,"usable_for_signing":false}`))
        case "/api/v1/local-signatures/clients/lookup":
            if r.Header.Get("Authorization")!="Bearer synthetic" { t.Error("missing bearer token") }
            _,_=w.Write([]byte(`{"status":"matched","client":{"borrower_id":"test-id","full_name":"Synthetic Person","signature_status":"missing","requires_capture":true},"may_reuse":false,"may_sign_contract":false}`))
        default:
            t.Errorf("unexpected API path %q",r.URL.Path)
            http.NotFound(w,r)
        }
    }))
    defer api.Close()
    ui,err:=newPCUI(api.URL)
    if err!=nil { t.Fatal(err) }
    ui.transport=api.Client()
    cookie,csrf,_:=localUIGet(t,ui)
    result:=localUIPost(ui,cookie,"/login",url.Values{
        "csrf":{csrf},"phone":{"59000000"},"password":{"synthetic-password"},
        "company":{companyID},
    },pcUIOrigin)
    if result.Code!=200 || !strings.Contains(result.Body.String(),"Signature status") ||
        strings.Contains(result.Body.String(),"synthetic-password") ||
        strings.Contains(result.Body.String(),"Bearer synthetic") {
        t.Fatal("operator login UI failed or credentials leaked")
    }
    result=localUIPost(ui,cookie,"/lookup",url.Values{
        "csrf":{csrf},"national_id":{"SYNTHETIC-ID"},
    },pcUIOrigin)
    if result.Code!=200 || !strings.Contains(result.Body.String(),"Synthetic Person") ||
        !strings.Contains(result.Body.String(),"Physical capture is not yet activated") {
        t.Fatal("client lookup UI failed")
    }
    if calls!=3 { t.Fatalf("expected three backend calls, got %d",calls) }
    result=localUIPost(ui,cookie,"/logout",url.Values{"csrf":{csrf}},pcUIOrigin)
    if result.Code!=200 || !strings.Contains(result.Body.String(),"Operator sign in") ||
        strings.Contains(result.Body.String(),"Synthetic Person") { t.Fatal("logout leaked previous client") }
}

func TestPCUIMaliciousBrowserCannotSubmitWithoutSession(t *testing.T) {
    ui,err:=newPCUI("https://loanhub.example")
    if err!=nil { t.Fatal(err) }
    request:=httptest.NewRequest(http.MethodPost,pcUIOrigin+"/login",
        strings.NewReader("phone=59000000&password=x"))
    request.Header.Set("Origin",pcUIOrigin)
    request.Header.Set("Content-Type","application/x-www-form-urlencoded")
    recorder:=httptest.NewRecorder()
    ui.ServeHTTP(recorder,request)
    if recorder.Code!=403 { t.Fatal("login allowed without session cookie") }
}


func TestPCUIRejectsSessionWhenOperatorAuthorizationCheckFails(t *testing.T) {
    companyID := "4236a21f-5164-48aa-90f3-a35eccd23ae2"
    api := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        w.Header().Set("Content-Type", "application/json")
        switch r.URL.Path {
        case "/api/v1/auth/login":
            _, _ = w.Write([]byte(`{"access_token":"synthetic","token_type":"bearer","user":{"is_active":true,"id":"operator","memberships":[{"company_id":"`+companyID+`","is_active":true}]}}`))
        case "/api/v1/local-signatures/me/status":
            http.Error(w, "Forbidden", http.StatusForbidden)
        default:
            t.Fatalf("unexpected API request %s", r.URL.Path)
        }
    }))
    defer api.Close()
    ui, err := newPCUI(api.URL)
    if err != nil { t.Fatal(err) }
    ui.transport = api.Client()
    cookie, csrf, _ := localUIGet(t, ui)
    result := localUIPost(ui, cookie, "/login", url.Values{
        "csrf": {csrf}, "phone": {"59000000"}, "password": {"synthetic-password"},
    }, pcUIOrigin)
    body := result.Body.String()
    if !strings.Contains(body, "Access denied") || !strings.Contains(body, "Operator sign in") ||
        strings.Contains(body, "Find a client") || strings.Contains(body, "Bearer synthetic") {
        t.Fatal("unauthorized operator retained an authenticated local session")
    }
}

func TestPCUISwitchOperatorClearsPreviousCaptureAndClient(t *testing.T) {
    companyID := "4236a21f-5164-48aa-90f3-a35eccd23ae2"
    api := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        w.Header().Set("Content-Type", "application/json")
        switch r.URL.Path {
        case "/api/v1/auth/login":
            _, _ = w.Write([]byte(`{"access_token":"synthetic","token_type":"bearer","user":{"is_active":true,"id":"operator","memberships":[{"company_id":"`+companyID+`","is_active":true}]}}`))
        case "/api/v1/local-signatures/me/status":
            _, _ = w.Write([]byte(`{"operator_id":"operator","company_id":"`+companyID+`","signature_status":"missing","requires_capture":true,"usable_for_signing":false}`))
        default:
            t.Fatalf("unexpected API request %s", r.URL.Path)
        }
    }))
    defer api.Close()
    ui, err := newPCUI(api.URL)
    if err != nil { t.Fatal(err) }
    ui.transport = api.Client()
    cookie, csrf, _ := localUIGet(t, ui)
    result := localUIPost(ui, cookie, "/login", url.Values{
        "csrf": {csrf}, "phone": {"59000000"}, "password": {"synthetic-password"},
    }, pcUIOrigin)
    if !strings.Contains(result.Body.String(), "Operator status") {
        t.Fatal("synthetic login failed")
    }
    session, ok := ui.sessions[cookie.Value]
    if !ok { t.Fatal("missing local session") }
    session.mu.Lock()
    session.lastClient = &LoanHubClientLookup{Status: "matched", Client: &LoanHubClientIdentity{
        BorrowerID: "synthetic", FullName: "PRIVATE PERSON", SignatureStatus: "missing",
    }}
    session.feedback = "private"
    session.mu.Unlock()
    result = localUIPost(ui, cookie, "/switch-operator", url.Values{"csrf": {csrf}}, pcUIOrigin)
    if result.Code != 200 || !strings.Contains(result.Body.String(), "Next operator must sign in") ||
        strings.Contains(result.Body.String(), "PRIVATE PERSON") || strings.Contains(result.Body.String(), "Find a client") {
        t.Fatal("operator switch failed to clear previous operator's data")
    }
    session.mu.Lock()
    defer session.mu.Unlock()
    if session.client != nil || session.status != nil || session.lastClient != nil ||
        session.capture != nil || len(session.reviewQueue) != 0 {
        t.Fatal("operator switch retained sensitive session state")
    }
}


func TestPCUIWorkstationKeyModeDeniesUnenrolledOperator(t *testing.T) {
    companyID := "4236a21f-5164-48aa-90f3-a35eccd23ae2"
    var calls []string
    api := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter,r *http.Request) {
        calls=append(calls,r.URL.Path)
        w.Header().Set("Content-Type","application/json")
        switch r.URL.Path {
        case "/api/v1/auth/login":
            _,_=w.Write([]byte(`{"access_token":"synthetic","token_type":"bearer","user":{"is_active":true,"id":"operator","memberships":[{"company_id":"`+companyID+`","is_active":true}]}}`))
        case "/api/v1/contract-signing/workstations/12345678-1234-4234-8234-123456789012/my-assignment":
            http.Error(w,"Forbidden",http.StatusForbidden)
        default:
            t.Fatalf("Unauthorized operator unexpectedly reached: %s",r.URL.Path)
        }
    }))
    defer api.Close()
    ui,err:=newPCUI(api.URL)
    if err!=nil{t.Fatal(err)}
    ui.transport=api.Client()
    ui.workstationKeyDir=filepath.Join(t.TempDir(),"unprovisioned")
    cookie,csrf,_:=localUIGet(t,ui)
    result:=localUIPost(ui,cookie,"/login",url.Values{
        "csrf":{csrf},"phone":{"59000000"},"password":{"synthetic-password"},
    },pcUIOrigin)
    if result.Code!=200 || !strings.Contains(result.Body.String(),"Access denied") ||
        strings.Contains(result.Body.String(),"Find a client") {
        t.Fatal("Unprovisioned identity allowed access")
    }
    if len(calls)!=1 {t.Fatalf("Only login expected, got %d backend calls",len(calls))}
    session:=ui.sessions[cookie.Value]
    if session.client!=nil {t.Fatal("Access token retained after device verification failed")}
}

func TestPCUIWorkstationProofRejectsWrongAssignmentBeforeOperatorStatus(t *testing.T) {
    companyID := "4236a21f-5164-48aa-90f3-a35eccd23ae2"
    dir:=filepath.Join(t.TempDir(),"identity")
    if err:=os.Mkdir(dir,0700);err!=nil{t.Fatal(err)}
    identity,err:=initializeWorkstationIdentity(dir)
    if err!=nil{t.Fatal(err)}
    count:=0
    api:=httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter,r *http.Request) {
        count++
        w.Header().Set("Content-Type","application/json")
        switch r.URL.Path {
        case "/api/v1/auth/login":
            _,_=w.Write([]byte(`{"access_token":"synthetic","token_type":"bearer","user":{"is_active":true,"id":"operator","memberships":[{"company_id":"`+companyID+`","is_active":true}]}}`))
        case "/api/v1/contract-signing/workstations/"+identity.WorkstationID+"/my-assignment":
            http.Error(w,"Forbidden",http.StatusForbidden)
        default:
            t.Fatalf("Disallowed employee reached %s",r.URL.Path)
        }
    }))
    defer api.Close()
    ui,err:=newPCUI(api.URL)
    if err!=nil{t.Fatal(err)}
    ui.transport=api.Client()
    ui.workstationKeyDir=dir
    cookie,csrf,_:=localUIGet(t,ui)
    result:=localUIPost(ui,cookie,"/login",url.Values{
        "csrf":{csrf},"phone":{"59000000"},"password":{"synthetic-password"},
    },pcUIOrigin)
    if result.Code!=200 || !strings.Contains(result.Body.String(),"Access denied") ||
        strings.Contains(result.Body.String(),"Find a client") {
        t.Fatal("Unassigned employee allowed bridge UI")
    }
    if count!=2 {t.Fatalf("Expected login plus assignment check only, got %d calls",count)}
    if ui.sessions[cookie.Value].client!=nil {t.Fatal("Rejected device retained token")}
}


func TestPCUIChromeSameOriginLoginAndStrictOrigin(t *testing.T) {
    ui,err:=newPCUI("https://loanhub.example")
    if err!=nil {t.Fatal(err)}
    cookie,csrf,html:=localUIGet(t,ui)
    if !strings.Contains(html,`<meta name="referrer" content="same-origin">`) {
        t.Fatal("local browser must preserve same-origin referrer policy")
    }
    req:=httptest.NewRequest(http.MethodGet,pcUIOrigin+"/",nil)
    response:=httptest.NewRecorder()
    ui.ServeHTTP(response,req)
    if got:=response.Header().Get("Referrer-Policy"); got!="same-origin" {
        t.Fatalf("unexpected referrer policy: %q",got)
    }
    payload:=url.Values{"csrf":{csrf},"phone":{"59000000"},"password":{"synthetic-password"}}
    for _,origin:=range []string{"null","","https://evil.example","http://localhost:8767"} {
        post:=localUIPost(ui,cookie,"/login",payload,origin)
        if post.Code!=http.StatusForbidden {
            t.Fatalf("origin %q unexpectedly accepted: %d",origin,post.Code)
        }
    }
    post:=localUIPost(ui,cookie,"/login",payload,pcUIOrigin)
    if post.Code!=http.StatusOK {
        t.Fatalf("same-origin login POST blocked: %d",post.Code)
    }
}
