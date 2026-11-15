package main

import "testing"

func TestContractsForSelectedLoanRejectsOtherBorrowerLoans(t *testing.T) {
    selected:="12345678-1234-4234-8234-123456789012"
    other:="22345678-1234-4234-8234-123456789012"
    contracts:=[]LoanHubEligibleContract{
        {ContractID:"a",LoanID:other},
        {ContractID:"b",LoanID:selected},
        {ContractID:"c",LoanID:other},
    }
    filtered:=contractsForSelectedLoan(contracts,selected)
    if len(filtered)!=1 || filtered[0].ContractID!="b" {
        t.Fatalf("wrong loan contract offered: %+v",filtered)
    }
    if got:=contractsForSelectedLoan(contracts,"32345678-1234-4234-8234-123456789012");len(got)!=0 {
        t.Fatalf("unknown loan must have no eligible contracts: %+v",got)
    }
    if got:=contractsForSelectedLoan(contracts,"");len(got)!=3 {
        t.Fatalf("manual borrower lookup should preserve choices: %+v",got)
    }
}
