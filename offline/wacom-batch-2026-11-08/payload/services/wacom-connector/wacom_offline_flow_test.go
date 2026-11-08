package main

import (
    "strings"
    "testing"
    "time"
)

func TestWacomLocalAuthorityRejectsLegacyAndExpiry(t *testing.T) {
    c := &LoanHubPCClient{accessToken:"synthetic",companyID:"tenant",operatorID:"employee"}
    if c.CheckWacomLocalAuthority(WacomCaptureOperation,time.Now())==nil {
        t.Fatal("Legacy PC mode permitted protected capture")
    }
    c.workstationKeyDir="/private/workstation"
    c.bridgeSessionToken="wb1_synthetic"
    c.bridgeSessionExpires=time.Now().Add(-time.Second)
    if c.CheckWacomLocalAuthority(WacomCaptureOperation,time.Now())==nil {
        t.Fatal("Expired workstation session permitted capture")
    }
    c.bridgeSessionExpires=time.Now().Add(time.Minute)
    if err:=c.CheckWacomLocalAuthority(WacomUploadOperation,time.Now());err!=nil {
        t.Fatal(err)
    }
    if c.CheckWacomLocalAuthority(WacomLocalOperation("sign-contract"),time.Now())==nil {
        t.Fatal("Local UI should not possess implicit sign-contract operation")
    }
}

func TestUnsafeDocumentSigningFlagsAreRejected(t *testing.T) {
    i:=LoanHubDocumentIntent{IntentID:"12345678-1234-4234-8234-123456789012",
        CompanyID:"22345678-1234-4234-8234-123456789012",
        BorrowerID:"32345678-1234-4234-8234-123456789012",
        ContractID:"42345678-1234-4234-8234-123456789012",
        DocumentSHA256:strings.Repeat("a",64),BindingSHA256:strings.Repeat("b",64),
        Status:"verified",SigningAuthorized:true}
    if assertSafeIntent(i)==nil{t.Fatal("Server attempted implicit document signing")}
    i.SigningAuthorized=false
    if err:=assertSafeIntent(i);err!=nil{t.Fatal(err)}
}
