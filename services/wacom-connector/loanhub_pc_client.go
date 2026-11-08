package main

// LoanHubPCClient is the direct HTTPS client used by the local Wacom PC app.
// It does not start a VPS bridge, persist credentials or authorize signing.
import (
    "bytes"
    "context"
    "crypto/ed25519"
    "crypto/sha256"
    "encoding/base64"
    "encoding/hex"
    "encoding/json"
    "errors"
    "fmt"
    "io"
    "net/http"
    "net/url"
    "os"
    "strings"
    "time"
)

const maxLoanHubResponse = 64 * 1024

type LoanHubPCClient struct {
    base *url.URL
    http *http.Client
    accessToken string // in-memory only; never log or persist
    companyID string
    operatorID string // derived only from the authenticated LoanHub response
    workstationKeyDir string // optional secure PC mode, never browser supplied
    bridgeSessionToken string // in-memory only; never log or persist
    bridgeSessionExpires time.Time
}

type LoanHubLoginResult struct {
    AccessToken string `json:"access_token"`
    TokenType string `json:"token_type"`
    User struct {
        ID string `json:"id"`
        MustChangePassword bool `json:"must_change_password"`
        IsActive bool `json:"is_active"`
        Memberships []struct {
            CompanyID string `json:"company_id"`
            IsActive bool `json:"is_active"`
        } `json:"memberships"`
    } `json:"user"`
}

type LoanHubOperatorStatus struct {
    OperatorID string `json:"operator_id"`
    FullName *string `json:"full_name"`
    CompanyID string `json:"company_id"`
    SignatureStatus string `json:"signature_status"`
    RequiresCapture bool `json:"requires_capture"`
    UsableForSigning bool `json:"usable_for_signing"`
}

type LoanHubClientIdentity struct {
    BorrowerID string `json:"borrower_id"`
    FullName string `json:"full_name"`
    SignatureStatus string `json:"signature_status"`
    RequiresCapture bool `json:"requires_capture"`
}

type LoanHubClientLookup struct {
    Status string `json:"status"`
    Client *LoanHubClientIdentity `json:"client"`
    MayReuse bool `json:"may_reuse"`
    MaySignContract bool `json:"may_sign_contract"`
}

type LoanHubCaptureReceipt struct {
    Status string `json:"status"`
    FileID string `json:"file_id"`
    Duplicate bool `json:"duplicate"`
    UsableForSigning bool `json:"usable_for_signing"`
}

// NewLoanHubPCClient enforces a fixed HTTPS origin; relative redirects cannot
// send credentials to other hosts. Test clients may provide their own TLS trust.
func NewLoanHubPCClient(server string, transport *http.Client) (*LoanHubPCClient, error) {
    parsed, err := url.Parse(server)
    if err != nil || parsed.Scheme != "https" || parsed.Hostname() == "" ||
        parsed.User != nil || parsed.RawQuery != "" || parsed.Fragment != "" ||
        parsed.Path != "" || parsed.RawPath != "" ||
        strings.HasSuffix(parsed.Host, ".") || parsed.Opaque != "" {
        return nil, errors.New("LoanHub origin must be an HTTPS hostname without path, credentials or query")
    }
    if transport == nil {
        transport = &http.Client{Timeout: 15 * time.Second}
    }
    clone := *transport
    clone.Timeout = 15 * time.Second
    clone.CheckRedirect = func(_ *http.Request, _ []*http.Request) error {
        return http.ErrUseLastResponse
    }
    return &LoanHubPCClient{base: parsed, http: &clone}, nil
}

func (c *LoanHubPCClient) do(ctx context.Context, method, path string, payload any, protected bool, result any) error {
    var body io.Reader
    if payload != nil {
        encoded, err := json.Marshal(payload)
        if err != nil { return errors.New("cannot encode request") }
        body = bytes.NewReader(encoded)
    }
    req, err := http.NewRequestWithContext(ctx, method, c.base.String()+path, body)
    if err != nil { return errors.New("cannot construct LoanHub request") }
    req.Header.Set("Accept", "application/json")
    if payload != nil { req.Header.Set("Content-Type", "application/json") }
    if protected && (strings.HasPrefix(path,"/api/v1/local-signatures/") || strings.HasPrefix(path,"/api/v1/wacom-document-intents")) && c.workstationKeyDir == "" && os.Getenv("LOANHUB_WACOM_PC_STRICT") == "1" {
        return errors.New("Secure device identity required for Wacom PC API")
    }
    if protected && (strings.HasPrefix(path,"/api/v1/local-signatures/") || strings.HasPrefix(path,"/api/v1/wacom-document-intents")) && c.workstationKeyDir != "" {
        // Re-prove the same workstation when its 5-minute capability has
        // expired; renewal is a fresh server challenge, never token replay.
        if c.bridgeSessionToken == "" || !time.Now().Add(15*time.Second).Before(c.bridgeSessionExpires) {
            c.bridgeSessionToken = ""
            c.bridgeSessionExpires = time.Time{}
            if err := c.VerifyLocalWorkstation(ctx,c.workstationKeyDir); err != nil {
                return errors.New("Wacom workstation session renewal failed")
            }
        }
        if c.bridgeSessionToken == "" || !time.Now().Before(c.bridgeSessionExpires) {
            return errors.New("Verified Wacom workstation session required")
        }
        req.Header.Set("X-Wacom-Bridge-Session", c.bridgeSessionToken)
    }
    if protected {
        if c.accessToken == "" || c.companyID == "" { return errors.New("LoanHub login and active company selection required") }
        req.Header.Set("Authorization", "Bearer "+c.accessToken)
        req.Header.Set("X-Company-ID", c.companyID)
    }
    resp, err := c.http.Do(req)
    if err != nil { return errors.New("LoanHub HTTPS request failed") }
    defer resp.Body.Close()
    if resp.StatusCode < 200 || resp.StatusCode > 299 {
        // Never expose backend response body, tokens, phone, National ID or name.
        return fmt.Errorf("LoanHub request rejected (HTTP %d)", resp.StatusCode)
    }
    limited := io.LimitReader(resp.Body, maxLoanHubResponse+1)
    encoded, err := io.ReadAll(limited)
    if err != nil || len(encoded) > maxLoanHubResponse { return errors.New("LoanHub response too large or unreadable") }
    if err := json.Unmarshal(encoded, result); err != nil { return errors.New("LoanHub returned invalid JSON") }
    return nil
}

// Login uses existing LoanHub login (phone/password, optional OTP).
// The selected company must belong to the authenticated user's active memberships.
func (c *LoanHubPCClient) Login(ctx context.Context, phone, password, otp, companyID string) error {
    c.Logout()
    if phone == "" || password == "" { return errors.New("phone and password are required") }
    var result LoanHubLoginResult
    request := struct {
        Phone string `json:"phone"`
        Password string `json:"password"`
        OTP string `json:"otp,omitempty"`
        DeviceName string `json:"device_name"`
    }{phone, password, otp, "LoanHub Wacom Local PC"}
    if err := c.do(ctx, http.MethodPost, "/api/v1/auth/login", request, false, &result); err != nil { return err }
    if result.TokenType != "bearer" || result.AccessToken == "" ||
       result.User.ID == "" || !result.User.IsActive || result.User.MustChangePassword {
        return errors.New("LoanHub login requires account action or returned invalid credentials")
    }
    // Never trust a company identifier supplied by the browser. For the
    // two-field login, derive the tenant only from authenticated memberships.
    // Existing callers may explicitly select an authorized company.
    selected := ""
    activeCount := 0
    authorized := false
    seen := make(map[string]bool)
    for _, membership := range result.User.Memberships {
        if !membership.IsActive || strings.TrimSpace(membership.CompanyID) == "" { continue }
        if companyID != "" && membership.CompanyID == companyID { authorized = true }
        if !seen[membership.CompanyID] {
            activeCount++
            seen[membership.CompanyID] = true
            selected = membership.CompanyID
        }
    }
    if companyID == "" {
        if activeCount != 1 { return errors.New("Exactly one active company membership required for automatic selection") }
        companyID = selected
    } else if !authorized {
        return errors.New("Selected company is not an active LoanHub membership")
    }
    c.accessToken = result.AccessToken
    c.companyID = companyID
    c.operatorID = result.User.ID
    return nil
}

func (c *LoanHubPCClient) Logout() {
    c.accessToken = ""
    c.companyID = ""
    c.operatorID = ""
    c.workstationKeyDir = ""
    c.bridgeSessionToken = ""
    c.bridgeSessionExpires = time.Time{}
}

func (c *LoanHubPCClient) OperatorSignatureStatus(ctx context.Context) (LoanHubOperatorStatus, error) {
    var response LoanHubOperatorStatus
    if err := c.do(ctx, http.MethodGet, "/api/v1/local-signatures/me/status", nil, true, &response); err != nil {
        return LoanHubOperatorStatus{}, err
    }
    // A status response is not a signing authorization. Fail closed even if
    // a misconfigured backend starts returning an unexpected permission.
    switch response.SignatureStatus {
    case "missing", "pending_review", "verified_capture":
    default:
        return LoanHubOperatorStatus{}, errors.New("Unexpected operator signature status")
    }
    if response.OperatorID == "" || response.CompanyID != c.companyID ||
        response.UsableForSigning || response.RequiresCapture != (response.SignatureStatus == "missing") {
        return LoanHubOperatorStatus{}, errors.New("Unsafe operator status returned by LoanHub")
    }
    return response, nil
}

func (c *LoanHubPCClient) FindClient(ctx context.Context, nationalID string) (LoanHubClientLookup, error) {
    var response LoanHubClientLookup
    nationalID = strings.TrimSpace(nationalID)
    if len(nationalID) < 4 || len(nationalID) > 50 {
        return response, errors.New("Client National ID must be 4 to 50 characters")
    }
    if err := c.do(ctx, http.MethodPost, "/api/v1/local-signatures/clients/lookup",
        map[string]string{"national_id": nationalID}, true, &response); err != nil {
        return LoanHubClientLookup{}, err
    }
    if response.MayReuse || response.MaySignContract {
        return LoanHubClientLookup{}, errors.New("LoanHub returned unsafe client signing permissions")
    }
    switch response.Status {
    case "not_found", "conflict":
        if response.Client != nil {
            return LoanHubClientLookup{}, errors.New("LoanHub exposed unexpected client identity")
        }
    case "matched":
        if response.Client == nil || response.Client.BorrowerID == "" ||
            strings.TrimSpace(response.Client.FullName) == "" {
            return LoanHubClientLookup{}, errors.New("LoanHub client identity is incomplete")
        }
        switch response.Client.SignatureStatus {
        case "missing", "pending_review", "verified_capture", "active":
        default:
            return LoanHubClientLookup{}, errors.New("Unexpected client signature status")
        }
        if response.Client.RequiresCapture != (response.Client.SignatureStatus == "missing") {
            return LoanHubClientLookup{}, errors.New("Inconsistent client capture requirements")
        }
    default:
        return LoanHubClientLookup{}, errors.New("Unexpected LoanHub client lookup result")
    }
    return response, nil
}

// UploadPNG requires the operator to have verified the correct signer and
// recorded consent locally. Approval and contract signing are separate processes.
func (c *LoanHubPCClient) UploadPNG(ctx context.Context, signerKind, borrowerID, consentReference string, png []byte) (LoanHubCaptureReceipt, error) {
    var response LoanHubCaptureReceipt
    if signerKind != "operator" && signerKind != "client" { return response, errors.New("Invalid signer kind") }
    if signerKind == "client" && borrowerID == "" { return response, errors.New("Client borrower ID required") }
    if signerKind == "operator" && borrowerID != "" { return response, errors.New("Operator capture cannot use borrower ID") }
    if len(strings.TrimSpace(consentReference)) < 4 { return response, errors.New("Consent reference required") }
    if len(png) == 0 || len(png) > 128000 || !bytes.HasPrefix(png, []byte{137, 80, 78, 71, 13, 10, 26, 10}) {
        return response, errors.New("Valid PNG capture required (maximum 128 KB)")
    }
    sum := sha256.Sum256(png)
    payload := map[string]any{
        "signer_kind": signerKind,
        "consent_reference": consentReference,
        "capture_png_base64": base64.StdEncoding.EncodeToString(png),
        "capture_sha256": hex.EncodeToString(sum[:]),
    }
    if signerKind == "client" { payload["borrower_id"] = borrowerID }
    err := c.do(ctx, http.MethodPost, "/api/v1/local-signatures/captures", payload, true, &response)
    if err != nil { return response, err }
    if response.Status != "pending_review" || response.UsableForSigning || response.FileID == "" {
        return LoanHubCaptureReceipt{}, errors.New("Unsafe or incomplete signature receipt")
    }
    return response, nil
}


// LoanHubWorkstationAssignment is an informational assignment response.
// It explicitly does not grant an authenticated bridge session or signing.
type LoanHubWorkstationAssignment struct {
    Assigned bool `json:"assigned"`
    WorkstationID string `json:"workstation_id"`
    OperatorID string `json:"operator_id"`
    BridgeSessionAuthorized bool `json:"bridge_session_authorized"`
    DeviceProofRequired bool `json:"device_proof_required"`
    SigningAuthorized bool `json:"signing_authorized"`
}

// CheckWorkstationAssignment checks that this *authenticated operator* has a
// current company-scoped assignment to the specified workstation. This check
// alone does NOT prove device possession; it MUST NOT authorize capture,
// lending operations, or signing until the backend issues a verified
// workstation-bound session.
func (c *LoanHubPCClient) CheckWorkstationAssignment(ctx context.Context, workstationID string) error {
    if !validUUID(workstationID) || c.operatorID == "" || c.companyID == "" {
        return errors.New("Authenticated operator and valid workstation ID required")
    }
    var result LoanHubWorkstationAssignment
    if err := c.do(ctx, http.MethodGet,
        "/api/v1/contract-signing/workstations/"+workstationID+"/my-assignment",
        nil, true, &result); err != nil {
        return err
    }
    if !result.Assigned || result.WorkstationID != workstationID ||
        result.OperatorID != c.operatorID || result.BridgeSessionAuthorized ||
        !result.DeviceProofRequired || result.SigningAuthorized {
        return errors.New("LoanHub workstation assignment response invalid or unauthorized")
    }
    return nil
}


// LoanHubBridgeChallenge is a server-issued challenge, not a browser-provided
// authorization. All fields must match the authenticated LoanHub identity.
type LoanHubBridgeChallenge struct {
    ChallengeID string `json:"challenge_id"`
    CompanyID string `json:"company_id"`
    EmployeeUserID string `json:"employee_user_id"`
    WorkstationID string `json:"workstation_id"`
    Nonce string `json:"nonce"`
    ExpiresAt string `json:"expires_at"`
    DeviceProofRequired bool `json:"device_proof_required"`
    SigningAuthorized bool `json:"signing_authorized"`
}

type LoanHubBridgeProofReceipt struct {
    DeviceProofVerified bool `json:"device_proof_verified"`
    EmployeeUserID string `json:"employee_user_id"`
    WorkstationID string `json:"workstation_id"`
    BridgeSessionAuthorized bool `json:"bridge_session_authorized"`
    CaptureAuthorized bool `json:"capture_authorized"`
    ContractSigned bool `json:"contract_signed"`
    BridgeSessionToken string `json:"bridge_session_token"`
    BridgeSessionExpiresAt string `json:"bridge_session_expires_at"`
}

// VerifyLocalWorkstation is a one-time device-possession proof with LoanHub's
// existing login, tenant context and server-issued nonce. The private key never
// goes over the network. This DOES NOT grant permission to originate a loan,
// capture a client's signature, or sign a contract.
func (c *LoanHubPCClient) VerifyLocalWorkstation(ctx context.Context, directory string) error {
    c.bridgeSessionToken = ""
    c.bridgeSessionExpires = time.Time{}
    if c.operatorID == "" || c.companyID == "" {
        return errors.New("LoanHub operator login is required")
    }
    workstationID, privateKey, err := loadWorkstationIdentity(directory)
    if err != nil { return errors.New("Secure local workstation identity unavailable") }
    if len(privateKey) != ed25519.PrivateKeySize { return errors.New("Workstation private key invalid") }
    if err := c.CheckWorkstationAssignment(ctx, workstationID); err != nil { return err }
    var challenge LoanHubBridgeChallenge
    if err := c.do(ctx,http.MethodPost,"/api/v1/wacom-bridge/device-challenges",
        map[string]string{"workstation_id":workstationID},true,&challenge);err!=nil{return err}
    if challenge.WorkstationID != workstationID ||
       challenge.CompanyID != c.companyID ||
       challenge.EmployeeUserID != c.operatorID ||
       !challenge.DeviceProofRequired || challenge.SigningAuthorized ||
       !validUUID(challenge.ChallengeID) {
        return errors.New("Untrusted workstation challenge scope")
    }
    nonce, err := base64.RawURLEncoding.Strict().DecodeString(challenge.Nonce)
    if err != nil || len(nonce) != 32 { return errors.New("Invalid server challenge nonce") }
    expiry, err := time.Parse(time.RFC3339Nano,challenge.ExpiresAt)
    if err != nil || !expiry.After(time.Now()) || expiry.After(time.Now().Add(31*time.Second)) {
        return errors.New("Server challenge expired or invalid")
    }
    // This byte sequence must match LoanHub's backend proof_message verbatim.
    message := fmt.Sprintf("LOANHUB-WACOM-BRIDGE-DEVICE-V1\n%s\n%s\n%s\n%s\n%s\n%d\n",
        c.companyID,c.operatorID,workstationID,challenge.ChallengeID,
        challenge.Nonce,expiry.Unix())
    sig := ed25519.Sign(privateKey,[]byte(message))
    var receipt LoanHubBridgeProofReceipt
    if err:=c.do(ctx,http.MethodPost,"/api/v1/wacom-bridge/device-proofs",
        map[string]string{
            "challenge_id":challenge.ChallengeID,
            "workstation_id":workstationID,
            "signature_base64":base64.StdEncoding.EncodeToString(sig),
        },true,&receipt);err!=nil{return err}
    if !receipt.DeviceProofVerified ||
       receipt.EmployeeUserID!=c.operatorID ||
       receipt.WorkstationID!=workstationID ||
       !receipt.BridgeSessionAuthorized ||
       receipt.CaptureAuthorized ||
       receipt.ContractSigned {
        return errors.New("Unsafe or invalid workstation proof receipt")
    }
    tokenBytes, tokenErr := base64.RawURLEncoding.Strict().DecodeString(strings.TrimPrefix(receipt.BridgeSessionToken,"wb1_"))
    validPrefix := strings.HasPrefix(receipt.BridgeSessionToken,"wb1_") && len(receipt.BridgeSessionToken)==47
    expires, timeErr := time.Parse(time.RFC3339Nano,receipt.BridgeSessionExpiresAt)
    now := time.Now()
    if !validPrefix || tokenErr != nil || len(tokenBytes)!=32 ||
       timeErr != nil || !expires.After(now.Add(10*time.Second)) ||
       expires.After(now.Add(5*time.Minute+30*time.Second)) {
        return errors.New("Invalid Wacom workstation session credential")
    }
    c.bridgeSessionToken = receipt.BridgeSessionToken
    c.bridgeSessionExpires = expires
    return nil
}


// RevokeBridgeSession revokes the currently held device-proof-issued capability
// on LoanHub. It must run BEFORE Logout clears the local bearer token.
// No new session is issued by this method and no signing permission is granted.
func (c *LoanHubPCClient) RevokeBridgeSession(ctx context.Context) error {
    if c.bridgeSessionToken == "" {
        return nil // legacy session: no server-side device capability to revoke
    }
    if c.accessToken == "" || c.companyID == "" {
        return errors.New("Authenticated LoanHub operator required to revoke Wacom session")
    }
    var reply struct {
        Revoked bool `json:"revoked"`
        SigningAuthorized bool `json:"signing_authorized"`
    }
    token := c.bridgeSessionToken
    // The request is authenticated with both the normal LoanHub user bearer
    // and X-Wacom-Bridge-Session. The token is not logged or sent to a browser.
    err := c.doWithBridgeRevocation(ctx, token, &reply)
    if err != nil { return err }
    if !reply.Revoked || reply.SigningAuthorized {
        return errors.New("Invalid Wacom revocation response")
    }
    c.bridgeSessionToken = ""
    c.bridgeSessionExpires = time.Time{}
    return nil
}

func (c *LoanHubPCClient) doWithBridgeRevocation(ctx context.Context, token string, reply any) error {
    req, err := http.NewRequestWithContext(ctx,http.MethodPost,
        c.base.String()+"/api/v1/wacom-bridge/sessions/revoke",nil)
    if err != nil { return errors.New("Cannot construct Wacom revocation request") }
    req.Header.Set("Accept","application/json")
    req.Header.Set("Authorization","Bearer "+c.accessToken)
    req.Header.Set("X-Company-ID",c.companyID)
    req.Header.Set("X-Wacom-Bridge-Session",token)
    response, err := c.http.Do(req)
    if err != nil { return errors.New("Wacom revocation HTTPS request failed") }
    defer response.Body.Close()
    if response.StatusCode < 200 || response.StatusCode >= 300 {
        return fmt.Errorf("Wacom revocation rejected (HTTP %d)",response.StatusCode)
    }
    raw, err := io.ReadAll(io.LimitReader(response.Body, maxLoanHubResponse+1))
    if err!=nil || len(raw)>maxLoanHubResponse || json.Unmarshal(raw,reply)!=nil {
        return errors.New("Wacom revocation response invalid")
    }
    return nil
}
