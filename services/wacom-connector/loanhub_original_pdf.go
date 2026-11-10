package main

import (
    "context"
    "crypto/sha256"
    "encoding/hex"
    "errors"
    "io"
    "net/http"
    "time"
)

const maxWacomOriginalPDF = 20 * 1024 * 1024

// FetchOriginalContractPDF returns only the exact, authenticated and hash-bound
// ORIGINAL PDF for the current prepared document. This does not sign anything.
func (c *LoanHubPCClient) FetchOriginalContractPDF(
    ctx context.Context, intent LoanHubDocumentIntent,
) ([]byte, error) {
    if c == nil || c.base == nil || c.http == nil ||
        c.accessToken == "" || c.companyID == "" || c.operatorID == "" ||
        c.workstationKeyDir == "" || !validUUID(intent.IntentID) ||
        intent.CompanyID != c.companyID ||
        (intent.Status != "prepared" && intent.Status != "consented") ||
        len(intent.DocumentSHA256) != 64 {
        return nil, errors.New("Verified document and PC login required")
    }
    if c.bridgeSessionToken == "" ||
        !time.Now().Add(15*time.Second).Before(c.bridgeSessionExpires) {
        c.bridgeSessionToken=""
        c.bridgeSessionExpires=time.Time{}
        if err:=c.VerifyLocalWorkstation(ctx,c.workstationKeyDir);err!=nil {
            return nil, errors.New("Workstation authorization renewal failed")
        }
    }
    if c.bridgeSessionToken=="" || !time.Now().Before(c.bridgeSessionExpires) {
        return nil, errors.New("Authenticated workstation session unavailable")
    }
    req,err:=http.NewRequestWithContext(ctx,http.MethodGet,
        c.base.String()+"/api/v1/wacom-document-intents/"+intent.IntentID+"/source-pdf",nil)
    if err!=nil {return nil,errors.New("Invalid contract review request")}
    req.Header.Set("Authorization","Bearer "+c.accessToken)
    req.Header.Set("X-Company-ID",c.companyID)
    req.Header.Set("X-Wacom-Bridge-Session",c.bridgeSessionToken)
    req.Header.Set("Accept","application/pdf")
    response,err:=c.http.Do(req)
    if err!=nil{return nil,errors.New("Contract review connection failed")}
    defer response.Body.Close()
    if response.StatusCode!=http.StatusOK ||
        response.Header.Get("Content-Type")!="application/pdf" ||
        response.Header.Get("X-Wacom-Original-SHA256")!=intent.DocumentSHA256 ||
        response.Header.Get("X-Wacom-Signing-Authorized")!="false" ||
        response.ContentLength>maxWacomOriginalPDF {
        return nil, errors.New("Contract review denied or response is unsafe")
    }
    payload,err:=io.ReadAll(io.LimitReader(response.Body,maxWacomOriginalPDF+1))
    if err!=nil || len(payload)>maxWacomOriginalPDF ||
        len(payload)<5 || string(payload[:5])!="%PDF-" {
        return nil, errors.New("Original contract PDF unavailable")
    }
    digest:=sha256.Sum256(payload)
    if hex.EncodeToString(digest[:])!=intent.DocumentSHA256 {
        return nil, errors.New("Original contract PDF integrity mismatch")
    }
    return payload,nil
}
