package main

// Two-step, human-confirmed local STU-540 capture and LoanHub pending-review upload.
// Nothing is saved to the PC disk or signed into a contract.
import (
    "bytes"
    "context"
    "crypto/sha256"
    "encoding/hex"
    "net/http"
    "strings"
    "time"
)

type pcPendingCapture struct {
    preview disposableWacomPreview
    signerKind string
    borrowerID string
    documentIntentID string
    selectedLoanID string
    handwritingSHA256 string
    consentReference string
    Label string
    expires time.Time
}

// discardCapture clears the in-memory PNG before releasing its session.
// It never writes raw pen points or handwriting to a local file.
func (session *pcUISession) discardCapture() {
    if session.capture != nil {
        for i := range session.capture.preview.PNG {
            session.capture.preview.PNG[i] = 0
        }
        session.capture = nil
    }
}

func (ui *pcUI) captureRequest(r *http.Request, session *pcUISession) {
    session.discardCapture()
    session.lastDocumentCaptureID=""
    if ui.sdkCapture==nil || session.client==nil {
        session.feedback="Capture unavailable on this workstation"
        return
    }
    if r.PostForm.Get("consent")!="yes" {
        session.feedback="Signer consent must be confirmed"
        return
    }
    ref:=strings.TrimSpace(r.PostForm.Get("consent_reference"))
    if len(ref)<4 || len(ref)>180 {
        session.feedback="A valid consent evidence reference is required"
        return
    }
    if session.selectedLoanID!="" && (session.documentIntent==nil || strings.TrimSpace(session.documentIntent.IntentID)=="") {
        session.feedback="Review the selected loan PDF and record exact-document consent before capture";return
    }
    kind:=r.PostForm.Get("signer_kind")
    enteredName:=strings.TrimSpace(r.PostForm.Get("confirm_name"))
    signerName:=""
    borrowerID:=""
    switch kind {
    case "operator":
        if session.status==nil || !session.status.RequiresCapture ||
            session.status.FullName==nil {
            session.feedback="Operator signature status or name must be verified first"
            return
        }
        signerName=*session.status.FullName
    case "client":
        if session.lastClient==nil || session.lastClient.Status!="matched" ||
            session.lastClient.Client==nil ||
            (!session.lastClient.Client.RequiresCapture && session.documentIntent==nil) {
            session.feedback="Find a client requiring a signature first"
            return
        }
        signerName=session.lastClient.Client.FullName
        borrowerID=session.lastClient.Client.BorrowerID
    default:
        session.feedback="Invalid signer selection"
        return
    }
    if session.documentIntent!=nil {
        if kind!="client" || session.documentIntent.Status!="consented" ||
            session.documentIntent.BorrowerID!=borrowerID {
            session.feedback="Document intent and client capture do not match";return
        }
    }
    if session.documentIntent!=nil && session.documentIntent.Status=="consented" &&
        ref != session.documentIntent.ConsentReference {
        session.feedback="Capture consent reference must match exact document consent";return
    }
    if enteredName=="" || !strings.EqualFold(strings.Join(strings.Fields(enteredName)," "),
        strings.Join(strings.Fields(signerName)," ")) {
        session.feedback="Signer name does not match LoanHub identity"
        return
    }
    if !ui.captureMu.TryLock() {
        session.feedback="The STU-540 is already capturing another signature"
        return
    }
    defer ui.captureMu.Unlock()
    preview,err:=ui.sdkCapture()
    if err!=nil || len(preview.PNG)==0 || len(preview.PNG)>wacomPreviewMaxBytes ||
        !bytes.HasPrefix(preview.PNG,[]byte{137,80,78,71,13,10,26,10}) ||
        preview.ContactPoints<3 || preview.StrokeCount<1 {
        // SDK may return bytes even if capture metadata is invalid.
        // Wipe the rejected in-memory signature preview before returning.
        for i := range preview.PNG { preview.PNG[i] = 0 }
        session.feedback="STU capture failed. Please retry after checking the pad."
        return
    }
    intentID := ""
    if session.documentIntent != nil { intentID = session.documentIntent.IntentID }
    inkDigest := sha256.Sum256(preview.PNG)
    session.capture=&pcPendingCapture{
        preview:preview, signerKind:kind, borrowerID:borrowerID, documentIntentID:intentID, selectedLoanID:session.selectedLoanID, handwritingSHA256:hex.EncodeToString(inkDigest[:]),
        consentReference:ref, Label:signerName, expires:time.Now().Add(2*time.Minute),
    }
    session.feedback="Capture complete. Check handwriting with the signer, then explicitly approve upload or discard."
}

func (ui *pcUI) uploadRequest(ctx context.Context, r *http.Request, session *pcUISession) {
    if session.client==nil || session.capture==nil {
        session.feedback="Capture a signature first"
        return
    }
    capture:=session.capture
    // The document can change between physical capture and upload.
    // A stale capture must never be linked to a different contract intent.
    if (session.selectedLoanID != "" && (session.documentIntent == nil || strings.TrimSpace(session.documentIntent.IntentID) == "")) ||
        capture.selectedLoanID != session.selectedLoanID ||
        (session.documentIntent == nil && capture.documentIntentID != "") ||
        (session.documentIntent != nil &&
        (capture.documentIntentID == "" || capture.documentIntentID != session.documentIntent.IntentID ||
         capture.signerKind != "client" ||
            session.documentIntent.Status != "consented" ||
            capture.borrowerID != session.documentIntent.BorrowerID ||
            capture.consentReference != session.documentIntent.ConsentReference)) {
        session.discardCapture()
        session.lastDocumentCaptureID = ""
        session.feedback = "Document consent changed; recapture handwriting for the exact document"
        return
    }
    if time.Now().After(capture.expires) {
        session.discardCapture()
        session.feedback="Capture expired; please capture again"
        return
    }
    if r.PostForm.Get("approved")!="yes" {
        session.feedback="Review of handwriting and consent confirmation required"
        return
    }
    currentDigest := sha256.Sum256(capture.preview.PNG)
    if capture.handwritingSHA256 == "" || capture.handwritingSHA256 != hex.EncodeToString(currentDigest[:]) {
        session.discardCapture()
        session.lastDocumentCaptureID = ""
        session.feedback = "Captured handwriting changed; recapture on the STU-540"
        return
    }
    if capture.signerKind=="operator" {
        if session.status==nil || !session.status.RequiresCapture {
            session.discardCapture()
            session.feedback="Operator is no longer eligible for capture"
            return
        }
    } else {
        if session.lastClient==nil || session.lastClient.Client==nil ||
            session.lastClient.Status!="matched" ||
            (!session.lastClient.Client.RequiresCapture && session.documentIntent==nil) ||
            session.lastClient.Client.BorrowerID!=capture.borrowerID {
            session.discardCapture()
            session.feedback="Client identity changed; capture discarded"
            return
        }
    }
    receipt,err:=session.client.UploadPNG(
        ctx,capture.signerKind,capture.borrowerID,capture.consentReference,capture.preview.PNG)
    if err!=nil || receipt.Status!="pending_review" || receipt.UsableForSigning {
        session.feedback="LoanHub did not confirm receipt; upload remains unapproved"
        return
    }
    if session.documentIntent!=nil && session.documentIntent.Status=="consented" &&
        capture.signerKind=="client" && capture.borrowerID==session.documentIntent.BorrowerID {
        session.lastDocumentCaptureID=receipt.FileID
    }
    session.discardCapture()
    session.lastClient=nil
    session.status=nil
    session.feedback="LoanHub received the capture for identity and consent review. It is not approved for signing."
}

