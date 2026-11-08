package main

// Offline companion for LoanHub Wacom per-document evidence.
// All calls require an existing signed workstation device session.
// A verified handwriting image is NOT a signed loan contract.
import (
    "context"
    "errors"
    "net/http"
    "time"
)

type LoanHubDocumentIntent struct {
    IntentID string `json:"intent_id"`
    CompanyID string `json:"company_id"`
    ContractID string `json:"contract_id"`
    BorrowerID string `json:"borrower_id"`
    DocumentSHA256 string `json:"document_sha256"`
    DocumentVersion string `json:"document_version"`
    BindingSHA256 string `json:"binding_sha256"`
    ConsentReference string `json:"consent_reference"`
    Status string `json:"status"`
    ExpiresAt time.Time `json:"expires_at"`
    SigningAuthorized bool `json:"signing_authorized"`
    SignedContractCreated bool `json:"signed_contract_created"`
    SignatureReuseAllowed bool `json:"signature_reuse_allowed"`
}

type LoanHubPrepareDocument struct {
    BorrowerID string `json:"borrower_id"`
    ContractID string `json:"contract_id"`
    SourceFileID string `json:"source_file_id"`
    WorkstationID string `json:"workstation_id"`
    DocumentVersion string `json:"document_version"`
}

// assertSafeIntent prevents the local UI from interpreting a document evidence
// record as an already signed or authorized contract.
func assertSafeIntent(intent LoanHubDocumentIntent) error {
    if !validUUID(intent.IntentID) || !validUUID(intent.ContractID) || !validUUID(intent.BorrowerID) ||
        !validUUID(intent.CompanyID) || len(intent.DocumentSHA256) != 64 ||
        len(intent.BindingSHA256) != 64 || intent.SigningAuthorized ||
        intent.SignedContractCreated || intent.SignatureReuseAllowed {
        return errors.New("Unsafe or incomplete document evidence response")
    }
    switch intent.Status {
    case "prepared", "consented", "evidence_uploaded", "verified", "rejected", "cancelled", "expired":
        return nil
    default:
        return errors.New("Unknown document evidence state")
    }
}

func (c *LoanHubPCClient) PrepareWacomDocument(ctx context.Context, req LoanHubPrepareDocument) (LoanHubDocumentIntent, error) {
    var intent LoanHubDocumentIntent
    if c.workstationKeyDir == "" || c.operatorID == "" || !validUUID(req.WorkstationID) ||
        !validUUID(req.BorrowerID) || !validUUID(req.ContractID) || !validUUID(req.SourceFileID) {
        return intent, errors.New("Authenticated private workstation and document identities required")
    }
    actualID, _, err := loadWorkstationIdentity(c.workstationKeyDir)
    if err != nil || actualID != req.WorkstationID {
        return intent, errors.New("Document requested on another workstation")
    }
    if err := c.do(ctx,http.MethodPost,"/api/v1/wacom-document-intents",req,true,&intent);err!=nil {return intent,err}
    if err:=assertSafeIntent(intent);err!=nil{return LoanHubDocumentIntent{},err}
    if intent.Status!="prepared" || intent.CompanyID!=c.companyID ||
        intent.ContractID!=req.ContractID || intent.BorrowerID!=req.BorrowerID ||
        intent.DocumentVersion!=req.DocumentVersion {
        return LoanHubDocumentIntent{},errors.New("Document intent identity mismatch")
    }
    return intent,nil
}

type LoanHubDocumentConsent struct {
    DisplayedDocumentSHA256 string `json:"displayed_document_sha256"`
    ConsentReference string `json:"consent_reference"`
    SignerConfirmation string `json:"signer_confirmation"`
}

func (c *LoanHubPCClient) ConfirmWacomDocumentConsent(ctx context.Context, intentID string, evidence LoanHubDocumentConsent) (LoanHubDocumentIntent,error) {
    var intent LoanHubDocumentIntent
    if !validUUID(intentID) || c.workstationKeyDir=="" ||
        evidence.SignerConfirmation!="I agree to sign this exact document" ||
        len(evidence.DisplayedDocumentSHA256)!=64 || len(evidence.ConsentReference)<4 {
        return intent,errors.New("Explicit document-specific consent evidence required")
    }
    if err:=c.do(ctx,http.MethodPost,"/api/v1/wacom-document-intents/"+intentID+"/consent",evidence,true,&intent);err!=nil{return intent,err}
    if err:=assertSafeIntent(intent);err!=nil{return LoanHubDocumentIntent{},err}
    if intent.Status!="consented" || intent.IntentID!=intentID ||
        intent.DocumentSHA256!=evidence.DisplayedDocumentSHA256 ||
        intent.ConsentReference != evidence.ConsentReference {
        return LoanHubDocumentIntent{},errors.New("Document consent response scope mismatch")
    }
    return intent,nil
}

func (c *LoanHubPCClient) AttachWacomDocumentEvidence(ctx context.Context, intentID, pendingCaptureFileID string) (LoanHubDocumentIntent,error) {
    var intent LoanHubDocumentIntent
    if !validUUID(intentID) || !validUUID(pendingCaptureFileID) || c.workstationKeyDir=="" {
        return intent,errors.New("Verified document intent and capture file required")
    }
    if err:=c.do(ctx,http.MethodPost,"/api/v1/wacom-document-intents/"+intentID+"/evidence",
        map[string]string{"evidence_file_id":pendingCaptureFileID},true,&intent);err!=nil{return intent,err}
    if err:=assertSafeIntent(intent);err!=nil{return LoanHubDocumentIntent{},err}
    if intent.Status!="evidence_uploaded" || intent.IntentID!=intentID {
        return LoanHubDocumentIntent{},errors.New("Document evidence state mismatch")
    }
    return intent,nil
}

// The existing SDK capture pipeline provides a local disposable PNG; it must be
// uploaded through the existing /local-signatures/captures quarantine path.
// This client only links the quarantined file to exact-document evidence.
// It never draws a signature onto a contract or writes a PDF.
