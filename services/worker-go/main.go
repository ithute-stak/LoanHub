package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"net/url"
	"os"
	"path"
	"strconv"
	"strings"
	"sync"
	"time"
)

type digestRequest struct {
	CorrelationID string `json:"correlation_id"`
	Payload       string `json:"payload"`
}

type digestResponse struct {
	CorrelationID string `json:"correlation_id"`
	SHA256        string `json:"sha256"`
}

type webhookDeliveryJob struct {
	JobID     string            `json:"job_id"`
	URL       string            `json:"url"`
	Headers   map[string]string `json:"headers"`
	Body      string            `json:"body"`
	TimeoutMS int               `json:"timeout_ms"`
}

type webhookDeliveryBatchRequest struct {
	Jobs []webhookDeliveryJob `json:"jobs"`
}

type webhookDeliveryResult struct {
	JobID              string `json:"job_id"`
	StatusCode         int    `json:"status_code"`
	ResponseBodySHA256 string `json:"response_body_sha256,omitempty"`
	Error              string `json:"error,omitempty"`
	DurationMS         int64  `json:"duration_ms"`
}

type webhookDeliveryBatchResponse struct {
	Authoritative bool                    `json:"authoritative"`
	Results       []webhookDeliveryResult `json:"results"`
}

type pushDeliveryJob struct {
	JobID     string            `json:"job_id"`
	Token     string            `json:"token"`
	Title     string            `json:"title"`
	Body      string            `json:"body"`
	ChannelID string            `json:"channel_id"`
	Data      map[string]string `json:"data"`
	TimeoutMS int               `json:"timeout_ms"`
}

type pushDeliveryBatchRequest struct {
	ProjectID   string            `json:"project_id"`
	AccessToken string            `json:"access_token"`
	Jobs        []pushDeliveryJob `json:"jobs"`
}

type pushDeliveryResult struct {
	JobID              string `json:"job_id"`
	StatusCode         int    `json:"status_code"`
	ResponseBodySHA256 string `json:"response_body_sha256,omitempty"`
	ProviderMessageID  string `json:"provider_message_id,omitempty"`
	Error              string `json:"error,omitempty"`
	DurationMS         int64  `json:"duration_ms"`
}

type pushDeliveryBatchResponse struct {
	Authoritative bool                 `json:"authoritative"`
	Results       []pushDeliveryResult `json:"results"`
}

func clampInt(value, minimum, maximum int) int {
	if value < minimum {
		return minimum
	}
	if value > maximum {
		return maximum
	}
	return value
}

func blockedIP(ip net.IP) bool {
	if ip == nil {
		return true
	}
	if ip.IsLoopback() || ip.IsPrivate() || ip.IsLinkLocalUnicast() || ip.IsLinkLocalMulticast() || ip.IsMulticast() || ip.IsUnspecified() {
		return true
	}
	if !ip.IsGlobalUnicast() {
		return true
	}
	// Carrier-grade NAT and benchmark/test networks are not valid webhook targets.
	_, cgnat, _ := net.ParseCIDR("100.64.0.0/10")
	_, benchmark4, _ := net.ParseCIDR("198.18.0.0/15")
	if cgnat.Contains(ip) || benchmark4.Contains(ip) {
		return true
	}
	return false
}

func validateRemoteURL(raw string) (*url.URL, error) {
	parsed, err := url.Parse(raw)
	if err != nil {
		return nil, err
	}
	if parsed.Scheme != "http" && parsed.Scheme != "https" {
		return nil, errors.New("unsupported scheme")
	}
	if parsed.Hostname() == "" || parsed.User != nil {
		return nil, errors.New("invalid webhook URL")
	}
	return parsed, nil
}

func publicDialContext(ctx context.Context, network, address string) (net.Conn, error) {
	host, port, err := net.SplitHostPort(address)
	if err != nil {
		return nil, err
	}
	resolved, err := net.DefaultResolver.LookupIPAddr(ctx, host)
	if err != nil {
		return nil, err
	}
	if len(resolved) == 0 {
		return nil, errors.New("host resolved to no addresses")
	}
	for _, item := range resolved {
		if blockedIP(item.IP) {
			return nil, fmt.Errorf("blocked webhook address: %s", item.IP.String())
		}
	}
	target := net.JoinHostPort(resolved[0].IP.String(), port)
	dialer := &net.Dialer{Timeout: 10 * time.Second, KeepAlive: 30 * time.Second}
	return dialer.DialContext(ctx, network, target)
}

func webhookHTTPClient() *http.Client {
	transport := &http.Transport{
		Proxy:               nil,
		DialContext:         publicDialContext,
		ForceAttemptHTTP2:   true,
		MaxIdleConns:        100,
		MaxIdleConnsPerHost: 20,
		IdleConnTimeout:     60 * time.Second,
	}
	return &http.Client{
		Transport: transport,
		CheckRedirect: func(_ *http.Request, _ []*http.Request) error {
			return http.ErrUseLastResponse
		},
	}
}

func deliverWebhook(client *http.Client, job webhookDeliveryJob) webhookDeliveryResult {
	started := time.Now()
	result := webhookDeliveryResult{JobID: job.JobID}

	parsed, err := validateRemoteURL(job.URL)
	if err != nil {
		result.Error = err.Error()
		result.DurationMS = time.Since(started).Milliseconds()
		return result
	}

	timeoutMS := clampInt(job.TimeoutMS, 100, 30_000)
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeoutMS)*time.Millisecond)
	defer cancel()

	request, err := http.NewRequestWithContext(ctx, http.MethodPost, parsed.String(), strings.NewReader(job.Body))
	if err != nil {
		result.Error = err.Error()
		result.DurationMS = time.Since(started).Milliseconds()
		return result
	}
	for key, value := range job.Headers {
		if strings.TrimSpace(key) != "" {
			request.Header.Set(key, value)
		}
	}

	response, err := client.Do(request)
	if err != nil {
		result.Error = err.Error()
		result.DurationMS = time.Since(started).Milliseconds()
		return result
	}
	defer response.Body.Close()

	result.StatusCode = response.StatusCode
	body, readErr := io.ReadAll(io.LimitReader(response.Body, 64*1024))
	if readErr != nil {
		result.Error = readErr.Error()
	} else {
		sum := sha256.Sum256(body)
		result.ResponseBodySHA256 = hex.EncodeToString(sum[:])
	}
	result.DurationMS = time.Since(started).Milliseconds()
	return result
}

func webhookConcurrency() int {
	raw := strings.TrimSpace(os.Getenv("LOANHUB_GO_HTTP_CONCURRENCY"))
	if raw == "" {
		return 16
	}
	value, err := strconv.Atoi(raw)
	if err != nil {
		return 16
	}
	return clampInt(value, 1, 64)
}

func handleWebhookDeliveryBatch(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	defer r.Body.Close()

	var req webhookDeliveryBatchRequest
	if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 8<<20)).Decode(&req); err != nil {
		http.Error(w, "invalid request", http.StatusBadRequest)
		return
	}
	if len(req.Jobs) == 0 || len(req.Jobs) > 100 {
		http.Error(w, "jobs must contain between 1 and 100 items", http.StatusUnprocessableEntity)
		return
	}

	seen := make(map[string]struct{}, len(req.Jobs))
	for _, job := range req.Jobs {
		if strings.TrimSpace(job.JobID) == "" || strings.TrimSpace(job.URL) == "" {
			http.Error(w, "job_id and url are required", http.StatusUnprocessableEntity)
			return
		}
		if len(job.Body) > 1<<20 {
			http.Error(w, "job body exceeds 1 MiB", http.StatusRequestEntityTooLarge)
			return
		}
		if _, exists := seen[job.JobID]; exists {
			http.Error(w, "duplicate job_id", http.StatusUnprocessableEntity)
			return
		}
		seen[job.JobID] = struct{}{}
	}

	client := webhookHTTPClient()
	results := make([]webhookDeliveryResult, len(req.Jobs))
	semaphore := make(chan struct{}, webhookConcurrency())
	var wait sync.WaitGroup

	for index, job := range req.Jobs {
		index := index
		job := job
		wait.Add(1)
		go func() {
			defer wait.Done()
			semaphore <- struct{}{}
			defer func() { <-semaphore }()
			results[index] = deliverWebhook(client, job)
		}()
	}
	wait.Wait()

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(webhookDeliveryBatchResponse{
		Authoritative: false,
		Results:       results,
	})
}

func pushConcurrency() int {
	raw := strings.TrimSpace(os.Getenv("LOANHUB_GO_PUSH_CONCURRENCY"))
	if raw == "" {
		return 32
	}
	value, err := strconv.Atoi(raw)
	if err != nil {
		return 32
	}
	return clampInt(value, 1, 128)
}

func validProjectID(value string) bool {
	value = strings.TrimSpace(value)
	return value != "" &&
		len(value) <= 128 &&
		!strings.ContainsAny(value, "/\\?#") &&
		!strings.ContainsAny(value, " \t\r\n")
}

func pushHTTPClient() *http.Client {
	transport := &http.Transport{
		Proxy:               http.ProxyFromEnvironment,
		ForceAttemptHTTP2:   true,
		MaxIdleConns:        128,
		MaxIdleConnsPerHost: 64,
		IdleConnTimeout:     60 * time.Second,
	}
	return &http.Client{Transport: transport}
}

func deliverPush(
	client *http.Client,
	projectID string,
	accessToken string,
	job pushDeliveryJob,
) pushDeliveryResult {
	started := time.Now()
	result := pushDeliveryResult{JobID: job.JobID}

	timeoutMS := clampInt(job.TimeoutMS, 100, 30_000)
	ctx, cancel := context.WithTimeout(
		context.Background(),
		time.Duration(timeoutMS)*time.Millisecond,
	)
	defer cancel()

	payload := map[string]any{
		"message": map[string]any{
			"token": job.Token,
			"notification": map[string]string{
				"title": job.Title,
				"body":  job.Body,
			},
			"data": job.Data,
			"android": map[string]any{
				"priority": "HIGH",
				"notification": map[string]any{
					"channel_id":               job.ChannelID,
					"sound":                    "default",
					"default_vibrate_timings": true,
				},
			},
		},
	}
	raw, err := json.Marshal(payload)
	if err != nil {
		result.Error = "encode_push_payload"
		result.DurationMS = time.Since(started).Milliseconds()
		return result
	}

	endpoint := fmt.Sprintf(
		"https://fcm.googleapis.com/v1/projects/%s/messages:send",
		path.Clean(projectID),
	)
	request, err := http.NewRequestWithContext(
		ctx,
		http.MethodPost,
		endpoint,
		strings.NewReader(string(raw)),
	)
	if err != nil {
		result.Error = err.Error()
		result.DurationMS = time.Since(started).Milliseconds()
		return result
	}
	request.Header.Set("Authorization", "Bearer "+accessToken)
	request.Header.Set("Content-Type", "application/json")

	response, err := client.Do(request)
	if err != nil {
		result.Error = err.Error()
		result.DurationMS = time.Since(started).Milliseconds()
		return result
	}
	defer response.Body.Close()

	result.StatusCode = response.StatusCode
	body, readErr := io.ReadAll(io.LimitReader(response.Body, 64*1024))
	if readErr != nil {
		result.Error = readErr.Error()
	} else {
		sum := sha256.Sum256(body)
		result.ResponseBodySHA256 = hex.EncodeToString(sum[:])
		if response.StatusCode >= 200 && response.StatusCode < 300 {
			var decoded struct {
				Name string `json:"name"`
			}
			if json.Unmarshal(body, &decoded) == nil {
				result.ProviderMessageID = decoded.Name
			}
		} else {
			result.Error = fmt.Sprintf("FCM returned HTTP %d", response.StatusCode)
		}
	}
	result.DurationMS = time.Since(started).Milliseconds()
	return result
}

func handlePushDeliveryBatch(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	defer r.Body.Close()

	var req pushDeliveryBatchRequest
	if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 8<<20)).Decode(&req); err != nil {
		http.Error(w, "invalid request", http.StatusBadRequest)
		return
	}
	if !validProjectID(req.ProjectID) || strings.TrimSpace(req.AccessToken) == "" {
		http.Error(w, "project_id and access_token are required", http.StatusUnprocessableEntity)
		return
	}
	if len(req.Jobs) == 0 || len(req.Jobs) > 500 {
		http.Error(w, "jobs must contain between 1 and 500 items", http.StatusUnprocessableEntity)
		return
	}

	seen := make(map[string]struct{}, len(req.Jobs))
	for _, job := range req.Jobs {
		if strings.TrimSpace(job.JobID) == "" || strings.TrimSpace(job.Token) == "" {
			http.Error(w, "job_id and token are required", http.StatusUnprocessableEntity)
			return
		}
		if len(job.Token) > 4096 || len(job.Title) > 120 || len(job.Body) > 240 {
			http.Error(w, "push field exceeds limit", http.StatusUnprocessableEntity)
			return
		}
		if _, exists := seen[job.JobID]; exists {
			http.Error(w, "duplicate job_id", http.StatusUnprocessableEntity)
			return
		}
		seen[job.JobID] = struct{}{}
	}

	client := pushHTTPClient()
	results := make([]pushDeliveryResult, len(req.Jobs))
	semaphore := make(chan struct{}, pushConcurrency())
	var wait sync.WaitGroup
	for index, job := range req.Jobs {
		index := index
		job := job
		wait.Add(1)
		go func() {
			defer wait.Done()
			semaphore <- struct{}{}
			defer func() { <-semaphore }()
			results[index] = deliverPush(client, req.ProjectID, req.AccessToken, job)
		}()
	}
	wait.Wait()

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(pushDeliveryBatchResponse{
		Authoritative: false,
		Results:       results,
	})
}

func main() {
	if len(os.Args) > 1 && os.Args[1] == "--healthcheck" {
		response, err := http.Get("http://127.0.0.1:8081/health/ready")
		if err != nil || response.StatusCode != http.StatusOK {
			os.Exit(1)
		}
		_ = response.Body.Close()
		return
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/health/ready", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"status":"ready","runtime":"go"}`))
	})
	mux.HandleFunc("/v1/digest", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		defer r.Body.Close()
		var req digestRequest
		if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<20)).Decode(&req); err != nil {
			http.Error(w, "invalid request", http.StatusBadRequest)
			return
		}
		sum := sha256.Sum256([]byte(req.Payload))
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(digestResponse{
			CorrelationID: req.CorrelationID,
			SHA256:        hex.EncodeToString(sum[:]),
		})
	})
	mux.HandleFunc("/v1/webhooks/deliver-batch", handleWebhookDeliveryBatch)
	mux.HandleFunc("/v1/push/deliver-batch", handlePushDeliveryBatch)

	addr := os.Getenv("LOANHUB_GO_WORKER_ADDR")
	if addr == "" {
		addr = ":8081"
	}
	log.Printf("LoanHub Go worker listening on %s", addr)
	log.Fatal(http.ListenAndServe(addr, mux))
}
