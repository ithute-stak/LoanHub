package main

import (
 "strings"
 "testing"
)

func TestWacomSocketStrictAdmissionFrames(t *testing.T){
 approved:=`{"type":"authorize_preview","preview_ticket":"`+strings.Repeat("x",128)+`","field_id":"borrower_signature"}`
 parsed,err:=decodeWacomPreviewRequest([]byte(approved))
 if err!=nil||parsed.FieldID!="borrower_signature"||parsed.PreviewTicket!=strings.Repeat("x",128){
  t.Fatalf("legitimate browser authorization frame rejected: %v",err)
 }
 for _,bad:=range []string{
  approved[:len(approved)-1]+`,"company_id":"forged"}`,
  approved[:len(approved)-1]+`,"workstation_id":"forged"}`,
  approved+"{}",
  approved+" garbage",
  `{"type":"authorize_preview","preview_ticket":"x","field_id":"borrower_signature","session_key":"spoof"}`,
  strings.Repeat("x",maxWacomWSMessageBytes+1),
  "",
 }{
  if _,err:=decodeWacomPreviewRequest([]byte(bad));err==nil{
   t.Fatalf("malformed browser first frame accepted: %.100q",bad)
  }
 }
 cancel,err:=decodeWacomPreviewRequest([]byte(`{"type":"cancel"}`))
 if err!=nil||cancel.Type!="cancel"{t.Fatalf("cancel frame rejected: %v",err)}
}
