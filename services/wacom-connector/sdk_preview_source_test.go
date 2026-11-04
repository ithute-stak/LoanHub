package main

import (
    "context"
    "errors"
    "os"
    "path/filepath"
    "testing"
    "time"
)

func TestSDKPreviewSourceNeverRunsWithoutBoundedAuthorizationContext(t *testing.T) {
    s:=wacomSDKPreviewSource{Executable:"/definitely/missing"}
    if err:=s.CollectPreview(context.Background(),func(p penSample)error{return nil});err==nil{
        t.Fatal("unbounded source accepted")
    }
    ctx,cancel:=context.WithCancel(context.Background())
    cancel()
    if err:=s.CollectPreview(ctx,func(p penSample)error{return nil});!errors.Is(err,context.Canceled){
        t.Fatalf("cancelled lease result: %v",err)
    }
    timed,stop:=context.WithTimeout(context.Background(),time.Second)
    defer stop()
    if err:=s.CollectPreview(timed,func(p penSample)error{return nil});err==nil{
        t.Fatal("short-lived SDK lease accepted")
    }
}

func TestSDKPreviewSourceRejectsUnsafeSDKExecutable(t *testing.T){
    ctx,cancel:=context.WithTimeout(context.Background(),20*time.Second)
    defer cancel()
    for _,name:=range []string{"relative/binary","/tmp/has spaces",""}{
        err:=(wacomSDKPreviewSource{Executable:name}).CollectPreview(ctx,func(p penSample)error{return nil})
        if err==nil {t.Errorf("unsafe executable %q accepted",name)}
    }
    root:=t.TempDir()
    file:=filepath.Join(root,"fakeSDK")
    if err:=os.WriteFile(file,[]byte("not a program"),0600);err!=nil{t.Fatal(err)}
    err:=(wacomSDKPreviewSource{Executable:file}).CollectPreview(ctx,func(p penSample)error{return nil})
    if err==nil {t.Fatal("non executable SDK file accepted")}
}

func TestCancelledContextCannotStartSDKProcess(t *testing.T) {
    root:=t.TempDir()
    script:=filepath.Join(root,"fakeSdk")
    if err:=os.WriteFile(script,[]byte("#!/bin/sh\necho should-not-run\n"),0700);err!=nil{t.Fatal(err)}
    ctx,cancel:=context.WithCancel(context.Background())
    cancel()
    err:=(wacomSDKPreviewSource{Executable:script}).CollectPreview(ctx,func(p penSample)error{return nil})
    if !errors.Is(err,context.Canceled){t.Fatalf("unexpected result %v",err)}
}
