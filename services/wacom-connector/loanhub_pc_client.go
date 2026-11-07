package main

// LoanHubPCClient is the direct HTTPS client used by the local Wacom PC app.
// It does not start a VPS bridge, persist credentials or authorize signing.
import (
    "bytes"
    "context"
    "crypto/sha256"
    "encoding/base64"
    "encoding/hex"
    "encoding/json"
    "errors"
    "fmt"
    "io"
    "net/http"
    "net/url"
    "strings"
    "time"
)

const maxLoanHubResponse = 64 * 1024

type LoanHubPCClient struct {
    base *url.URL
    http *http.Client
    accessToken string // in-memory only; never log or persist
    companyID string
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
    if phone == "" || password == "" || companyID == "" { return errors.New("phone, password and company are required") }
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
    authorized := false
    for _, membership := range result.User.Memberships {
        if membership.IsActive && membership.CompanyID == companyID { authorized = true; break }
    }
    if !authorized { return errors.New("Selected company is not an active LoanHub membership") }
    c.accessToken = result.AccessToken
    c.companyID = companyID
    return nil
}

func (c *LoanHubPCClient) Logout() {
    c.accessToken = ""
    c.companyID = ""
}

func (c *LoanHubPCClient) OperatorSignatureStatus(ctx context.Context) (LoanHubOperatorStatus, error) {
    var response LoanHubOperatorStatus
    err := c.do(ctx, http.MethodGet, "/api/v1/local-signatures/me/status", nil, true, &response)
    return response, err
}

func (c *LoanHubPCClient) FindClient(ctx context.Context, nationalID string) (LoanHubClientLookup, error) {
    var response LoanHubClientLookup
    if len(strings.TrimSpace(nationalID)) < 4 { return response, errors.New("Client National ID required") }
    err := c.do(ctx, http.MethodPost, "/api/v1/local-signatures/clients/lookup",
        map[string]string{"national_id": strings.TrimSpace(nationalID)}, true, &response)
    return response, err
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
