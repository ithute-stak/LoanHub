package main

// Two-step, human-confirmed local STU-540 capture and LoanHub pending-review upload.
// Nothing is saved to the PC disk or signed into a contract.
import (
    "bytes"
    "context"
    "net/http"
    "strings"
    "time"
)

type pcPendingCapture struct {
    preview disposableWacomPreview
    signerKind string
    borrowerID string
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
            session.lastClient.Client==nil || !session.lastClient.Client.RequiresCapture {
            session.feedback="Find a client requiring a signature first"
            return
        }
        signerName=session.lastClient.Client.FullName
        borrowerID=session.lastClient.Client.BorrowerID
    default:
        session.feedback="Invalid signer selection"
        return
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
    session.capture=&pcPendingCapture{
        preview:preview, signerKind:kind, borrowerID:borrowerID,
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
    if time.Now().After(capture.expires) {
        session.discardCapture()
        session.feedback="Capture expired; please capture again"
        return
    }
    if r.PostForm.Get("approved")!="yes" {
        session.feedback="Review of handwriting and consent confirmation required"
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
            session.lastClient.Status!="matched" || !session.lastClient.Client.RequiresCapture ||
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
    session.discardCapture()
    session.lastClient=nil
    session.status=nil
    session.feedback="LoanHub received the capture for identity and consent review. It is not approved for signing."
}

