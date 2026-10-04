package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"log"
	"net/http"
	"os"
)

type digestRequest struct {
	CorrelationID string `json:"correlation_id"`
	Payload       string `json:"payload"`
}

type digestResponse struct {
	CorrelationID string `json:"correlation_id"`
	SHA256        string `json:"sha256"`
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
			SHA256: hex.EncodeToString(sum[:]),
		})
	})

	addr := os.Getenv("LOANHUB_GO_WORKER_ADDR")
	if addr == "" {
		addr = ":8081"
	}
	log.Printf("LoanHub Go worker listening on %s", addr)
	log.Fatal(http.ListenAndServe(addr, mux))
}
