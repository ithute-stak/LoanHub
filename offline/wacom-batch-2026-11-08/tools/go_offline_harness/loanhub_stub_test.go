package main

import (
  "context"
  "crypto/ed25519"
  "errors"
  "net/http"
  "regexp"
  "time"
)

type LoanHubPCClient struct {
  accessToken string
  companyID string
  operatorID string
  workstationKeyDir string
  bridgeSessionToken string
  bridgeSessionExpires time.Time
}
func (c *LoanHubPCClient) do(ctx context.Context, method,path string,payload any, protected bool,result any) error {
  return errors.New("offline Go harness deliberately rejects remote calls")
}
func loadWorkstationIdentity(directory string)(string,ed25519.PrivateKey,error) {
  return "",nil,errors.New("no physical workstation key available in offline harness")
}
func validUUID(v string) bool {
  return regexp.MustCompile(`^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$`).MatchString(v)
}
var _ = http.MethodPost

// Minimal compile-only local UI adapter for the offline source package.
type pcUI struct {workstationKeyDir string}
type pcUISession struct {
    client *LoanHubPCClient
    lastClient *LoanHubClientLookup
    documentIntent *LoanHubDocumentIntent
    lastDocumentCaptureID string
    feedback string
}
type LoanHubClientLookup struct {Status string; Client *LoanHubClientIdentity}
type LoanHubClientIdentity struct {BorrowerID string}
