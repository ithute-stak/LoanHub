package main

// Local-only Wacom evidence desk. A document intent never authorizes PDF
// signing, disbursement or reusing employee handwriting by default.
import (
    "context"
    "net/http"
    "strings"
)

func (ui *pcUI) documentContractsRequest(ctx context.Context,s *pcUISession) {
    s.discardCapture()
    s.forgetDocument()
    s.eligibleContracts=nil
    if s.client==nil || s.lastClient==nil || s.lastClient.Status!="matched" ||
        s.lastClient.Client==nil || ui.workstationKeyDir=="" {
        s.feedback="Authenticated workstation and borrower lookup required"
        return
    }
    contracts,err:=s.client.EligibleWacomContracts(ctx,s.lastClient.Client.BorrowerID)
    if err!=nil {
        s.feedback="No authorized contract list available for this borrower"
        return
    }
    s.eligibleContracts=contracts
    if len(contracts)==0 {
        s.feedback="No eligible unsigned contracts are available"
    } else {
        s.feedback="Choose a contract by number; LoanHub verifies the original PDF before consent"
    }
}

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
    selectedID:=strings.TrimSpace(r.PostForm.Get("contract_id"))
    var selected *LoanHubEligibleContract
    for i:=range s.eligibleContracts {
        if s.eligibleContracts[i].ContractID==selectedID {
            selected=&s.eligibleContracts[i]
            break
        }
    }
    if selected==nil || selected.BorrowerID!=s.lastClient.Client.BorrowerID {
        s.feedback="Select an eligible contract loaded for this borrower first"
        return
    }
    req:=LoanHubPrepareDocument{
        BorrowerID:s.lastClient.Client.BorrowerID,
        ContractID:selected.ContractID,
        SourceFileID:selected.SourceFileID,
        WorkstationID:workstationID,
        DocumentVersion:selected.DocumentVersion,
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
