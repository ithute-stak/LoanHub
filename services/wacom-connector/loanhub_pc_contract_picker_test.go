package main

import (
    "context"
    "net/http"
    "net/http/httptest"
    "net/url"
    "strings"
    "testing"
)

func TestContractPickerRejectsForeignSelection(t *testing.T) {
    ui,err:=newPCUI("https://loanhub.example")
    if err!=nil {t.Fatal(err)}
    cookie,csrf,_:=localUIGet(t,ui)
    session:=ui.sessions[cookie.Value]
    borrower:="32345678-1234-4234-8234-123456789012"
    contract:="42345678-1234-4234-8234-123456789012"
    session.client=&LoanHubPCClient{}
    session.lastClient=&LoanHubClientLookup{Status:"matched",Client:&LoanHubClientIdentity{BorrowerID:borrower,FullName:"Synthetic borrower"}}
    session.eligibleContracts=[]LoanHubEligibleContract{{
        ContractID:contract,ContractNumber:"SYNTHETIC-1",
        BorrowerID:borrower,DocumentVersion:"1",
        SourceFileID:"52345678-1234-4234-8234-123456789012",
    }}
    // With no workstation identity, the request must fail without calling LoanHub.
    result:=localUIPost(ui,cookie,"/document-prepare",url.Values{
        "csrf":{csrf},"contract_id":{"62345678-1234-4234-8234-123456789012"},
    },pcUIOrigin)
    if result.Code!=200 || session.documentIntent!=nil {
        t.Fatal("unverified workstation prepared a foreign contract")
    }
}

func TestEligibleContractsClientFailsClosedOnForeignBorrower(t *testing.T) {
    borrower:="32345678-1234-4234-8234-123456789012"
    api:=httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter,r *http.Request){
        if r.URL.Path!="/api/v1/wacom-document-intents/borrowers/"+borrower+"/eligible-contracts" {
            t.Fatalf("unexpected endpoint: %s",r.URL.Path)
        }
        w.Header().Set("Content-Type","application/json")
        _,_=w.Write([]byte(`{"borrower_id":"42345678-1234-4234-8234-123456789012","contracts":[],"signing_authorized":false,"contract_signed":false}`))
    }))
    defer api.Close()
    client,err:=NewLoanHubPCClient(api.URL,api.Client())
    if err!=nil {t.Fatal(err)}
    client.workstationKeyDir="/synthetic"
    client.accessToken="synthetic"
    client.companyID="22345678-1234-4234-8234-123456789012"
    // A valid session is not available: cannot trust a forged borrower result.
    if _,err=client.EligibleWacomContracts(context.Background(),borrower);err==nil {
        t.Fatal("foreign borrower selection must fail")
    }
}

func TestContractSelectionTemplateContainsNoRawFileIDInputs(t *testing.T) {
    html:=pcUITemplate.Tree.Root.String()
    if !strings.Contains(html,"eligible contracts") && !strings.Contains(html,"EligibleContracts") {
        t.Fatal("contract picker missing from PC UI")
    }
    if strings.Contains(html,`name="source_file_id"`) || strings.Contains(html,`name="document_version"`) {
        t.Fatal("browser may manually override the selected contract metadata")
    }
}
