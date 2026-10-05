package main

import (
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestValidateRemoteURL(t *testing.T) {
	if _, err := validateRemoteURL("https://example.com/webhook"); err != nil {
		t.Fatalf("expected https URL to be accepted: %v", err)
	}
	if _, err := validateRemoteURL("ftp://example.com/webhook"); err == nil {
		t.Fatal("expected ftp URL to be rejected")
	}
	if _, err := validateRemoteURL("https://user:pass@example.com/webhook"); err == nil {
		t.Fatal("expected embedded credentials to be rejected")
	}
}

func TestBlockedIP(t *testing.T) {
	for _, raw := range []string{"127.0.0.1", "10.0.0.1", "192.168.1.10", "169.254.1.1", "::1"} {
		if !blockedIP(net.ParseIP(raw)) {
			t.Fatalf("expected %s to be blocked", raw)
		}
	}
	if blockedIP(net.ParseIP("8.8.8.8")) {
		t.Fatal("expected public IP to be allowed")
	}
}

func TestWebhookBatchRejectsEmptyJobs(t *testing.T) {
	request := httptest.NewRequest(http.MethodPost, "/v1/webhooks/deliver-batch", strings.NewReader(`{"jobs":[]}`))
	recorder := httptest.NewRecorder()

	handleWebhookDeliveryBatch(recorder, request)

	if recorder.Code != http.StatusUnprocessableEntity {
		t.Fatalf("expected 422, got %d", recorder.Code)
	}
}

func TestWebhookBatchRejectsDuplicateJobIDs(t *testing.T) {
	body := `{"jobs":[
		{"job_id":"same","url":"https://example.com/a","headers":{},"body":"{}","timeout_ms":1000},
		{"job_id":"same","url":"https://example.com/b","headers":{},"body":"{}","timeout_ms":1000}
	]}`
	request := httptest.NewRequest(http.MethodPost, "/v1/webhooks/deliver-batch", strings.NewReader(body))
	recorder := httptest.NewRecorder()

	handleWebhookDeliveryBatch(recorder, request)

	if recorder.Code != http.StatusUnprocessableEntity {
		t.Fatalf("expected 422, got %d", recorder.Code)
	}
}

func TestWebhookConcurrencyBounds(t *testing.T) {
	t.Setenv("LOANHUB_GO_HTTP_CONCURRENCY", "999")
	if webhookConcurrency() != 64 {
		t.Fatalf("expected concurrency to clamp to 64, got %d", webhookConcurrency())
	}

	t.Setenv("LOANHUB_GO_HTTP_CONCURRENCY", "invalid")
	if webhookConcurrency() != 16 {
		t.Fatalf("expected invalid concurrency to fall back to 16, got %d", webhookConcurrency())
	}
}


func TestPushBatchRejectsInvalidProjectID(t *testing.T) {
	body := `{"project_id":"../bad","access_token":"short-lived","jobs":[{"job_id":"1","token":"device-token","data":{},"notification":{"title":"LoanHub","body":"Update"},"channel_id":"loanhub_events"}]}`
	request := httptest.NewRequest(http.MethodPost, "/v1/push/fcm-deliver-batch", strings.NewReader(body))
	recorder := httptest.NewRecorder()

	handlePushDeliveryBatch(recorder, request)

	if recorder.Code != http.StatusUnprocessableEntity {
		t.Fatalf("expected 422, got %d", recorder.Code)
	}
}

func TestPushBatchRejectsDuplicateJobIDs(t *testing.T) {
	body := `{"project_id":"loanhub-prod","access_token":"short-lived","jobs":[
		{"job_id":"same","token":"device-a","data":{},"notification":{"title":"LoanHub","body":"A"},"channel_id":"loanhub_events"},
		{"job_id":"same","token":"device-b","data":{},"notification":{"title":"LoanHub","body":"B"},"channel_id":"loanhub_events"}
	]}`
	request := httptest.NewRequest(http.MethodPost, "/v1/push/fcm-deliver-batch", strings.NewReader(body))
	recorder := httptest.NewRecorder()

	handlePushDeliveryBatch(recorder, request)

	if recorder.Code != http.StatusUnprocessableEntity {
		t.Fatalf("expected 422, got %d", recorder.Code)
	}
}

func TestFirebaseProjectIDPattern(t *testing.T) {
	if !firebaseProjectIDPattern.MatchString("loanhub-prod") {
		t.Fatal("expected normal Firebase project id to be accepted")
	}
	if firebaseProjectIDPattern.MatchString("LOANHUB_PROD") {
		t.Fatal("expected unsafe project id characters to be rejected")
	}
}
