package main

// Company-scoped, independent signature-evidence review on the LOCAL PC.
// All authorization is rechecked by LoanHub. Review never authorizes signing.
import (
    "bytes"
    "context"
    "errors"
    "fmt"
    "io"
    "net/http"
    "regexp"
    "strings"
)

var wacomUUID = regexp.MustCompile(`^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$`)

type LoanHubReviewCapture struct {
    CaptureFileID string `json:"capture_file_id"`
    CapturedByUserID *string `json:"captured_by_user_id"`
    CompanyID string `json:"company_id"`
    SignerKind string `json:"signer_kind"`
    SignerID string `json:"signer_id"`
    EvidenceStatus string `json:"evidence_status"`
    ScanStatus string `json:"scan_status"`
    UsableForSigning bool `json:"usable_for_signing"`
    AutomaticReuseAllowed bool `json:"automatic_reuse_allowed"`
}

type loanHubReviewList struct {
    Captures []LoanHubReviewCapture `json:"captures"`
}

func (c *LoanHubPCClient) ReviewQueue(ctx context.Context) ([]LoanHubReviewCapture,error) {
    var result loanHubReviewList
    err:=c.do(ctx,http.MethodGet,"/api/v1/local-signatures/review?limit=20",nil,true,&result)
    if err!=nil{return nil,err}
    if len(result.Captures)>20{return nil,errors.New("Invalid review queue size")}
    for _,record:=range result.Captures {
        if !wacomUUID.MatchString(record.CaptureFileID) ||
            record.CompanyID!=c.companyID || record.EvidenceStatus!="pending_review" ||
            record.ScanStatus!="clean" || record.UsableForSigning || record.AutomaticReuseAllowed {
            return nil,errors.New("Unsafe evidence review queue")
        }
    }
    return result.Captures,nil
}

func (c *LoanHubPCClient) ReviewPreview(ctx context.Context,fileID string)([]byte,error){
    if !wacomUUID.MatchString(fileID){return nil,errors.New("Invalid capture ID")}
    if c.accessToken=="" || c.companyID=="" {return nil,errors.New("Authenticated company required")}
    req,err:=http.NewRequestWithContext(ctx,http.MethodGet,
        c.base.String()+"/api/v1/local-signatures/review/"+fileID+"/preview",nil)
    if err!=nil{return nil,errors.New("Cannot create review request")}
    req.Header.Set("Authorization","Bearer "+c.accessToken)
    req.Header.Set("X-Company-ID",c.companyID)
    req.Header.Set("Accept","image/png")
    resp,err:=c.http.Do(req)
    if err!=nil{return nil,errors.New("LoanHub review preview unavailable")}
    defer resp.Body.Close()
    if resp.StatusCode!=http.StatusOK {return nil,fmt.Errorf("Review preview refused (HTTP %d)",resp.StatusCode)}
    if !strings.HasPrefix(resp.Header.Get("Content-Type"),"image/png") {
        return nil,errors.New("Review returned non-PNG content")
    }
    raw,err:=io.ReadAll(io.LimitReader(resp.Body,wacomPreviewMaxBytes+1))
    if err!=nil || len(raw)==0 || len(raw)>wacomPreviewMaxBytes ||
        !bytes.HasPrefix(raw,[]byte{137,80,78,71,13,10,26,10}) {
        return nil,errors.New("Invalid or oversized review image")
    }
    return raw,nil
}

func (c *LoanHubPCClient) ReviewDecision(ctx context.Context,fileID,decision,reference,reason string,
    identityChecked,consentChecked bool)(LoanHubReviewCapture,error){
    var result LoanHubReviewCapture
    if !wacomUUID.MatchString(fileID) || (decision!="verify" && decision!="reject") {
        return result,errors.New("Invalid review selection")
    }
    reference=strings.TrimSpace(reference)
    reason=strings.TrimSpace(reason)
    if len(reference)<4 || len(reference)>160 || len(reason)<8 || len(reason)>400 {
        return result,errors.New("Review reference and reason are required")
    }
    if decision=="verify" && (!identityChecked || !consentChecked) {
        return result,errors.New("Independent identity and consent checks are required")
    }
    payload:=map[string]any{
        "decision":decision,"identity_checked":identityChecked,
        "consent_checked":consentChecked,"evidence_reference":reference,"reason":reason,
    }
    err:=c.do(ctx,http.MethodPost,"/api/v1/local-signatures/review/"+fileID+"/decision",payload,true,&result)
    if err!=nil{return LoanHubReviewCapture{},err}
    expected:="verified"
    if decision=="reject"{expected="rejected"}
    if result.CaptureFileID!=fileID || result.CompanyID!=c.companyID ||
        result.EvidenceStatus!=expected || result.UsableForSigning || result.AutomaticReuseAllowed {
        return LoanHubReviewCapture{},errors.New("LoanHub returned an unsafe review decision")
    }
    return result,nil
}

func (ui *pcUI) refreshReviewQueue(ctx context.Context, session *pcUISession){
    session.reviewQueue=nil
    if session.client==nil {
        session.feedback="Sign in first"
        return
    }
    queue,err:=session.client.ReviewQueue(ctx)
    if err!=nil {
        // A staff member without company-management permissions may not review.
        session.feedback="Review queue unavailable or management access denied"
        return
    }
    session.reviewQueue=queue
    session.feedback="Pending evidence queue refreshed; review does not enable signing"
}

func (ui *pcUI) decideReview(ctx context.Context,r *http.Request,session *pcUISession){
    if session.client==nil {session.feedback="Sign in first";return}
    id:=r.PostForm.Get("file_id")
    present:=false
    for _,item:=range session.reviewQueue {
        if item.CaptureFileID==id {present=true;break}
    }
    if !present {session.feedback="Refresh the pending queue before reviewing";return}
    _,err:=session.client.ReviewDecision(
        ctx,id,r.PostForm.Get("decision"),r.PostForm.Get("evidence_reference"),
        r.PostForm.Get("reason"),r.PostForm.Get("identity_checked")=="yes",
        r.PostForm.Get("consent_checked")=="yes")
    session.reviewQueue=nil
    if err!=nil {
        session.feedback="Independent review refused; refresh and verify permissions"
        return
    }
    session.feedback="Evidence decision recorded by LoanHub. No document signing or reuse enabled."
}

func (ui *pcUI) serveReviewPreview(ctx context.Context,w http.ResponseWriter,
    session *pcUISession,fileID string){
    if session.client==nil || !wacomUUID.MatchString(fileID) {
        http.Error(w,"Review image unavailable",http.StatusNotFound)
        return
    }
    present:=false
    for _,item:=range session.reviewQueue {
        if item.CaptureFileID==fileID {present=true;break}
    }
    if !present {http.Error(w,"Review queue refresh required",http.StatusForbidden);return}
    data,err:=session.client.ReviewPreview(ctx,fileID)
    if err!=nil {http.Error(w,"Review image unavailable",http.StatusNotFound);return}
    w.Header().Set("Content-Type","image/png")
    w.Header().Set("Content-Disposition","inline; filename=review.png")
    w.Header().Set("Content-Security-Policy","default-src 'none'; sandbox")
    _,_=w.Write(data)
}
