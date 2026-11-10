package main

import (
    "context"
    "net/http"
)

// serveOriginalDocumentPreview is available only inside the loopback UI's
// authenticated, CSRF-protected session. Never exposes a bearer token or PDF
// URL directly to the browser, and never writes the PDF to disk.
func (ui *pcUI) serveOriginalDocumentPreview(ctx context.Context,w http.ResponseWriter,s *pcUISession) {
    if s.client==nil || s.documentIntent==nil ||
        s.documentIntent.Status!="prepared" || s.lastClient==nil ||
        s.lastClient.Status!="matched" || s.lastClient.Client==nil ||
        s.documentIntent.BorrowerID!=s.lastClient.Client.BorrowerID {
        http.Error(w,"Original contract review unavailable",http.StatusForbidden)
        return
    }
    pdf,err:=s.client.FetchOriginalContractPDF(ctx,*s.documentIntent)
    if err!=nil {
        http.Error(w,"LoanHub could not verify this original contract PDF",http.StatusConflict)
        return
    }
    w.Header().Set("Content-Type","application/pdf")
    w.Header().Set("Cache-Control","private, no-store, max-age=0")
    w.Header().Set("Pragma","no-cache")
    w.Header().Set("Content-Disposition",`inline; filename="loanhub-original-REVIEW-NOT-SIGNED.pdf"`)
    w.Header().Set("X-Wacom-Signing-Authorized","false")
    _,_=w.Write(pdf)
}
