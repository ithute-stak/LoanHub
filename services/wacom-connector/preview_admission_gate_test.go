package main

import (
    "crypto/ed25519"
    "crypto/rand"
    "errors"
    "strings"
    "testing"
    "time"
)

type testEnrolledWorkstation struct { id string; err error; calls int }
func (w *testEnrolledWorkstation) AuthenticatedWorkstationID() (string,error) {
    w.calls++
    return w.id,w.err
}

type testLivePreviewSession struct { calls int; rejectAt int }
func (s *testLivePreviewSession) CheckPreviewActive(scope previewTicketScope) error {
    s.calls++
    if s.rejectAt > 0 && s.calls >= s.rejectAt {
        return errors.New("session revoked")
    }
    return nil
}

func admissionTestSetup(t *testing.T) (string, previewTicketScope, time.Time, previewAdmissionDependencies) {
    t.Helper()
    pub, priv, err := ed25519.GenerateKey(rand.Reader)
    if err != nil { t.Fatal(err) }
    now := time.Date(2026,11,4,13,0,0,0,time.UTC)
    scope := testPreviewScope()
    token := previewTestToken(t, priv, now, scope)
    deps := previewAdmissionDependencies{
        Keys: map[string]ed25519.PublicKey{"test-ed25519-key":pub},
        Enrollment: &testEnrolledWorkstation{id:scope.WorkstationID},
        Session: &testLivePreviewSession{},
        Replay: &fakePreviewReplay{used:map[string]bool{}},
    }
    return token,scope,now,deps
}

func TestPreviewAdmissionRequiresEnrollmentSessionAndSingleUse(t *testing.T) {
    ticket, scope, now, deps := admissionTestSetup(t)
    if err := admitTemporaryWacomPreview(ticket,scope,now,deps); err != nil {
        t.Fatalf("authorized preview denied: %v",err)
    }
    if got := deps.Session.(*testLivePreviewSession).calls; got != 2 {
        t.Fatalf("expected double revocation check, got %d",got)
    }
    if err := admitTemporaryWacomPreview(ticket,scope,now,deps); err == nil {
        t.Fatal("replayed preview ticket accepted")
    }
}

func TestPreviewAdmissionRejectsUnenrolledWorkstationWithoutConsuming(t *testing.T) {
    ticket,scope,now,deps := admissionTestSetup(t)
    workstation := deps.Enrollment.(*testEnrolledWorkstation)
    workstation.id = "99999999-9999-9999-9999-999999999999"
    if err := admitTemporaryWacomPreview(ticket,scope,now,deps); err == nil {
        t.Fatal("workstation mismatch accepted")
    }
    if len(deps.Replay.(*fakePreviewReplay).used) != 0 {
        t.Fatal("rejected workstation consumed ticket")
    }
    workstation.id = scope.WorkstationID
    if err := admitTemporaryWacomPreview(ticket,scope,now,deps); err != nil {
        t.Fatalf("authentic enrolled workstation rejected: %v",err)
    }
}

func TestPreviewAdmissionRejectsRevocationBeforeAndDuringConsume(t *testing.T) {
    for _, rejectAt := range []int{1,2} {
        ticket,scope,now,deps := admissionTestSetup(t)
        sess := deps.Session.(*testLivePreviewSession)
        sess.rejectAt = rejectAt
        if err := admitTemporaryWacomPreview(ticket,scope,now,deps); err == nil {
            t.Fatalf("revocation at %d accepted",rejectAt)
        }
        used := len(deps.Replay.(*fakePreviewReplay).used)
        if rejectAt == 1 && used != 0 { t.Fatal("precheck rejection consumed ticket") }
        if rejectAt == 2 && used != 1 { t.Fatal("postcheck rejection must leave JTI consumed") }
    }
}

func TestPreviewAdmissionRejectsMissingDependenciesAndWrongScope(t *testing.T) {
    ticket,scope,now,deps := admissionTestSetup(t)
    deps.Replay = nil
    if err := admitTemporaryWacomPreview(ticket,scope,now,deps);err == nil {
        t.Fatal("missing replay store accepted")
    }
    ticket,scope,now,deps = admissionTestSetup(t)
    scope.ContractHash = strings.Repeat("b",64)
    if err := admitTemporaryWacomPreview(ticket,scope,now,deps);err == nil {
        t.Fatal("wrong contract hash accepted")
    }
    ticket,scope,now,deps = admissionTestSetup(t)
    deps.Enrollment = nil
    if err := admitTemporaryWacomPreview(ticket,scope,now,deps);err == nil {
        t.Fatal("missing workstation enrollment accepted")
    }
}
