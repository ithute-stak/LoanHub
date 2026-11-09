package main

// Local-only Wacom evidence desk. A document intent never authorizes PDF
// signing, disbursement or reusing employee handwriting by default.
import (
    "context"
    "net/http"
    "strings"
)

func (ui *pcUI) documentPrepareRequest(ctx context.Context,r *http.Request,s *pcUISession) {
    // Preparing a different contract invalidates any pending local handwriting.
    s.discardCapture()
    s.documentIntent=nil
    s.lastDocumentCaptureID=""
    if s.client==nil || s.lastClient==nil || s.lastClient.Status!="matched" ||
        s.lastClient.Client==nil || ui.workstationKeyDir=="" {
        s.feedback="Secure employee login and borrower lookup required";return
    }
    workstationID,_,err:=loadWorkstationIdentity(ui.workstationKeyDir)
    if err!=nil {s.feedback="Approved workstation identity unavailable";return}
    req:=LoanHubPrepareDocument{
        BorrowerID:s.lastClient.Client.BorrowerID,
        ContractID:strings.TrimSpace(r.PostForm.Get("contract_id")),
        SourceFileID:strings.TrimSpace(r.PostForm.Get("source_file_id")),
        WorkstationID:workstationID,
        DocumentVersion:strings.TrimSpace(r.PostForm.Get("document_version")),
    }
    doc,err:=s.client.PrepareWacomDocument(ctx,req)
    if err!=nil {s.feedback="Document unavailable or unauthorized. Verify contract, borrower and source PDF.";return}
    s.documentIntent=&doc
    s.feedback="Document reference prepared. Show the exact contract PDF to the borrower before requesting consent."
}

func (ui *pcUI) documentConsentRequest(ctx context.Context,r *http.Request,s *pcUISession) {
    if s.client==nil || s.documentIntent==nil || s.documentIntent.Status!="prepared" {
        s.feedback="Prepare an exact document first";return
    }
    if r.PostForm.Get("displayed_sha256")!=s.documentIntent.DocumentSHA256 ||
        r.PostForm.Get("signer_confirmed")!="yes" {
        s.feedback="Exact document hash and signer confirmation are required";return
    }
    doc,err:=s.client.ConfirmWacomDocumentConsent(ctx,s.documentIntent.IntentID,LoanHubDocumentConsent{
        DisplayedDocumentSHA256:s.documentIntent.DocumentSHA256,
        ConsentReference:strings.TrimSpace(r.PostForm.Get("document_consent_reference")),
        SignerConfirmation:"I agree to sign this exact document",
    })
    if err!=nil {s.feedback="Document consent not accepted. Review the document and begin again.";return}
    s.documentIntent=&doc
    s.feedback="Consent evidence recorded. Capture new handwriting with the client present. This is not a signed loan contract."
}

func (ui *pcUI) documentAttachRequest(ctx context.Context,s *pcUISession) {
    if s.client==nil || s.documentIntent==nil || s.documentIntent.Status!="consented" ||
        s.lastDocumentCaptureID=="" {
        s.feedback="Document consent and a new matching client capture are required";return
    }
    doc,err:=s.client.AttachWacomDocumentEvidence(ctx,s.documentIntent.IntentID,s.lastDocumentCaptureID)
    if err!=nil {s.feedback="Could not attach handwriting evidence; independent review required";return}
    s.documentIntent=&doc
    s.lastDocumentCaptureID=""
    s.feedback="Document-specific evidence linked. Await independent company review; no PDF has been signed."
}

func (s *pcUISession) forgetDocument() {
    s.documentIntent=nil
    s.lastDocumentCaptureID=""
}
