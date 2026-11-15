package main

import (
    "net/http"
    "net/url"
    "testing"
)

func TestBorrowerIDDeskRequiresAuthenticatedSessionAndCSRF(t *testing.T) {
    ui, err := newPCUI("https://loanhub.example")
    if err != nil { t.Fatal(err) }
    cookie, csrf, _ := localUIGet(t, ui)
    values := url.Values{
        "csrf": {csrf},
        "borrower_id": {"b8a9099b-694b-441b-b4a0-2d8394b7e62d"},
    }
    for _, origin := range []string{"", "https://attacker.example"} {
        response := localUIPost(ui, cookie, "/lookup-borrower", values, origin)
        if response.Code != http.StatusForbidden {
            t.Fatalf("foreign origin %q accepted: %d", origin, response.Code)
        }
    }
    values.Set("csrf", "wrong")
    response := localUIPost(ui, cookie, "/lookup-borrower", values, pcUIOrigin)
    if response.Code != http.StatusForbidden { t.Fatal("invalid CSRF accepted") }
    values.Set("csrf", csrf)
    response = localUIPost(ui, cookie, "/lookup-borrower", values, pcUIOrigin)
    if response.Code != http.StatusOK || !strings.Contains(response.Body.String(), "Sign in first") {
        t.Fatal("borrower-ID lookup allowed without operator authentication")
    }
}
