package main

import (
    "strings"
    "sync"
    "testing"
    "time"
)

func sampleScope() previewScope {
    return previewScope{
        CompanyID:"11111111-1111-4111-8111-111111111111",
        BorrowerID:"22222222-2222-4222-8222-222222222222",
        ContractID:"33333333-3333-4333-8333-333333333333",
        SessionID:"44444444-4444-4444-8444-444444444444",
        ContractSHA256:strings.Repeat("a",64),
    }
}

func TestPreviewLeaseOneTimeContractBound(t *testing.T) {
    now:=time.Now()
    scope:=sampleScope()
    lease,token,err:=createLocalPreviewLease(scope,time.Minute,now)
    if err != nil || len(token)<40 { t.Fatalf("creation: %v",err) }
    altered:=scope
    altered.CompanyID="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    if err:=lease.consume(altered,token,now);err==nil { t.Fatal("cross-company accepted") }
    altered=scope
    altered.ContractSHA256=strings.Repeat("b",64)
    if err:=lease.consume(altered,token,now);err==nil { t.Fatal("wrong contract digest accepted") }
    altered=scope
    altered.SessionID="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    if err:=lease.consume(altered,token,now);err==nil { t.Fatal("cross-session accepted") }
    if err:=lease.consume(scope,token+"x",now);err==nil { t.Fatal("wrong token accepted") }
    if err:=lease.consume(scope,token,now);err!=nil { t.Fatalf("correct scope rejected: %v",err) }
    if err:=lease.consume(scope,token,now);err==nil { t.Fatal("replay accepted") }
}

func TestPreviewLeaseExpiryRevocationAndInvalidCreation(t *testing.T) {
    now:=time.Now()
    scope:=sampleScope()
    lease,token,err:=createLocalPreviewLease(scope,time.Second,now)
    if err!=nil { t.Fatal(err) }
    if err:=lease.consume(scope,token,now.Add(time.Second));err==nil { t.Fatal("expired lease accepted") }
    revoked,token,err:=createLocalPreviewLease(scope,time.Minute,now)
    if err!=nil { t.Fatal(err) }
    revoked.revoke()
    if err:=revoked.consume(scope,token,now);err==nil { t.Fatal("revoked token accepted") }
    scope.ContractSHA256="NOT-A-SHA256"
    if _,_,err:=createLocalPreviewLease(scope,time.Minute,now);err==nil { t.Fatal("bad digest accepted") }
    if _,_,err:=createLocalPreviewLease(sampleScope(),time.Hour,now);err==nil { t.Fatal("unbounded lease accepted") }
}

func TestPreviewLeaseConcurrentReplayAllowsOnlyOne(t *testing.T) {
    now:=time.Now()
    scope:=sampleScope()
    lease,token,err:=createLocalPreviewLease(scope,time.Minute,now)
    if err!=nil { t.Fatal(err) }
    var wg sync.WaitGroup
    success:=make(chan struct{},20)
    for i:=0;i<20;i++ {
        wg.Add(1)
        go func(){
            defer wg.Done()
            if lease.consume(scope,token,now)==nil { success<-struct{}{} }
        }()
    }
    wg.Wait()
    if len(success)!=1 { t.Fatalf("expected one allowed preview, got %d",len(success)) }
}
