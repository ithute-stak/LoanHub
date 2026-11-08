import unittest
from dataclasses import replace
from datetime import datetime,timezone,timedelta
from decimal import Decimal as D
from uuid import UUID
from phase43_engine.operation_guard import OperationIntent,GuardError,validate_intent,ExecutionGate,assert_live_release_gate
from phase43_engine.provider_evidence_binding import ProviderEvidence,ExpectedOperation,EvidenceBindingError,bind_verified_evidence
from phase43_engine.dispute_recovery import DisputeCase,CaseState,CaseAction,DisputeError,advance
from phase43_engine.statement_matching import Entry,Outcome,match_statements,StatementError
from phase43_engine.release_manifest import ArtifactDigest,ReleaseManifest,ManifestError,verify_manifest

C=UUID('00000000-0000-4000-8000-000000000001')
L=UUID('00000000-0000-4000-8000-000000000002')
B=UUID('00000000-0000-4000-8000-000000000003')
OTHER=UUID('00000000-0000-4000-8000-000000000004')
NOW=datetime(2026,11,8,12,tzinfo=timezone.utc)
def intent():
    return OperationIntent(C,L,B,'operation_ref_123456789',D('100.00'),NOW-timedelta(days=1),C,L,B,D('150.00'),NOW+timedelta(days=1),False,'a'*64,'policy_v1')
def evidence():
    return ProviderEvidence('vodacom_mpesa_direct','evt_12345678','operation_ref_123456789',C,D('100.00'),'LSL','settled',NOW,'verification_12345678','f'*64,'confirmed')
def expected():return ExpectedOperation(C,'operation_ref_123456789',D('100.00'),'LSL','vodacom_mpesa_direct')
def dispute():return DisputeCase('case123456','operation_ref_123456789',CaseState.OPEN,0,D('100.00'),())
def entry(**kw):
    a=dict(company_id='companyA',provider_id='vodacom_mpesa_direct',provider_reference='event001',operation_id='operation1234',amount=D('100.00'),currency='LSL',status='settled');a.update(kw);return Entry(**a)
def manifest():return ReleaseManifest('a'*40,(ArtifactDigest('src/engine.py','b'*64),),'security_review_123',('provider_cert_1234',),'migration_approval_1','rollback_test_123','staging_test_123',True)

class Phase43Tests(unittest.TestCase):
    def test_mandate_valid(self):validate_intent(intent(),trusted_company_id=C,now=NOW)
    def test_mandate_cross_company(self):
        with self.assertRaises(GuardError):validate_intent(intent(),trusted_company_id=OTHER,now=NOW)
    def test_mandate_wrong_loan(self):
        with self.assertRaises(GuardError):validate_intent(replace(intent(),mandate_loan_id=OTHER),trusted_company_id=C,now=NOW)
    def test_mandate_revoked(self):
        with self.assertRaises(GuardError):validate_intent(replace(intent(),mandate_revoked=True),trusted_company_id=C,now=NOW)
    def test_mandate_expired(self):
        with self.assertRaises(GuardError):validate_intent(intent(),trusted_company_id=C,now=NOW+timedelta(days=2))
    def test_mandate_future(self):
        with self.assertRaises(GuardError):validate_intent(intent(),trusted_company_id=C,now=NOW-timedelta(days=2))
    def test_mandate_over_amount(self):
        with self.assertRaises(GuardError):validate_intent(replace(intent(),amount=D('151.00')),trusted_company_id=C,now=NOW)
    def test_mandate_nan(self):
        with self.assertRaises(GuardError):validate_intent(replace(intent(),amount=D('NaN')),trusted_company_id=C,now=NOW)
    def test_mandate_bad_cents(self):
        with self.assertRaises(GuardError):validate_intent(replace(intent(),amount=D('1.001')),trusted_company_id=C,now=NOW)
    def test_preview_never_authorizes(self):
        with self.assertRaises(GuardError):validate_intent(replace(intent(),preview_only=True),trusted_company_id=C,now=NOW)
    def test_evidence_valid(self):self.assertEqual(bind_verified_evidence(evidence(),expected(),verified_provider_id='vodacom_mpesa_direct',verified_event_id='evt_12345678'),'vodacom_mpesa_direct:evt_12345678')
    def test_evidence_provider_mismatch(self):
        with self.assertRaises(EvidenceBindingError):bind_verified_evidence(evidence(),expected(),verified_provider_id='golink_optional',verified_event_id='evt_12345678')
    def test_evidence_wrong_event(self):
        with self.assertRaises(EvidenceBindingError):bind_verified_evidence(evidence(),expected(),verified_provider_id='vodacom_mpesa_direct',verified_event_id='evt_other_123456')
    def test_evidence_unconfirmed(self):
        with self.assertRaises(EvidenceBindingError):bind_verified_evidence(replace(evidence(),provider_status='pending'),expected(),verified_provider_id='vodacom_mpesa_direct',verified_event_id='evt_12345678')
    def test_evidence_cross_tenant(self):
        with self.assertRaises(EvidenceBindingError):bind_verified_evidence(replace(evidence(),company_id=OTHER),expected(),verified_provider_id='vodacom_mpesa_direct',verified_event_id='evt_12345678')
    def test_evidence_amount(self):
        with self.assertRaises(EvidenceBindingError):bind_verified_evidence(replace(evidence(),amount=D('101.00')),expected(),verified_provider_id='vodacom_mpesa_direct',verified_event_id='evt_12345678')
    def test_dispute_reviewer(self):
        with self.assertRaises(DisputeError):advance(dispute(),CaseAction.BEGIN_REVIEW,expected_version=0,actor_id='x')
    def test_dispute_flow(self):
        a=advance(dispute(),CaseAction.BEGIN_REVIEW,expected_version=0,actor_id='reviewer_1');b=advance(a,CaseAction.REQUEST_PROVIDER_EVIDENCE,expected_version=1,actor_id='reviewer_1',evidence_ref='evidence_123456');c=advance(b,CaseAction.BEGIN_REVIEW,expected_version=2,actor_id='reviewer_1');d=advance(c,CaseAction.RESOLVE_MATCHED,expected_version=3,actor_id='reviewer_1',now=NOW);self.assertEqual(d.state,CaseState.RESOLVED_MATCHED)
    def test_dispute_no_evidence_resolution(self):
        a=advance(dispute(),CaseAction.BEGIN_REVIEW,expected_version=0,actor_id='reviewer_1')
        with self.assertRaises(DisputeError):advance(a,CaseAction.RESOLVE_MATCHED,expected_version=1,actor_id='reviewer_1',now=NOW)
    def test_dispute_reversal_approval(self):
        a=advance(dispute(),CaseAction.BEGIN_REVIEW,expected_version=0,actor_id='reviewer_1',evidence_ref='evidence_123456')
        with self.assertRaises(DisputeError):advance(a,CaseAction.RESOLVE_REVERSAL,expected_version=1,actor_id='reviewer_1',now=NOW)
    def test_dispute_version(self):
        with self.assertRaises(DisputeError):advance(dispute(),CaseAction.BEGIN_REVIEW,expected_version=9,actor_id='reviewer_1')
    def test_dispute_terminal(self):
        a=advance(dispute(),CaseAction.ESCALATE,expected_version=0,actor_id='reviewer_1')
        with self.assertRaises(DisputeError):advance(a,CaseAction.BEGIN_REVIEW,expected_version=1,actor_id='reviewer_1')
    def test_statement_match(self):self.assertEqual(match_statements((entry(),),(entry(),))[0].result,Outcome.MATCHED)
    def test_statement_provider_only(self):self.assertEqual(match_statements((),(entry(),))[0].result,Outcome.PROVIDER_ONLY)
    def test_statement_internal_only(self):self.assertEqual(match_statements((entry(),),())[0].result,Outcome.INTERNAL_ONLY)
    def test_statement_duplicate(self):self.assertEqual(match_statements((entry(),),(entry(),entry()))[0].result,Outcome.DUPLICATE_PROVIDER)
    def test_statement_amount(self):self.assertEqual(match_statements((entry(),),(entry(amount=D('110.00')),))[0].result,Outcome.AMOUNT_MISMATCH)
    def test_statement_currency(self):self.assertEqual(match_statements((entry(),),(entry(currency='USD'),))[0].result,Outcome.CURRENCY_MISMATCH)
    def test_statement_status(self):self.assertEqual(match_statements((entry(),),(entry(status='pending'),))[0].result,Outcome.STATUS_MISMATCH)
    def test_statement_tenant_split(self):self.assertEqual(len(match_statements((entry(),),(entry(company_id='companyB'),))),2)
    def test_statement_nan_fails(self):
        with self.assertRaises(StatementError):match_statements((entry(amount=D('NaN')),),())
    def test_manifest_valid(self):verify_manifest(manifest(),{'src/engine.py':'b'*64})
    def test_manifest_disabled(self):
        with self.assertRaises(ManifestError):verify_manifest(replace(manifest(),deployment_authorized=False),{'src/engine.py':'b'*64})
    def test_manifest_modified(self):
        with self.assertRaises(ManifestError):verify_manifest(manifest(),{'src/engine.py':'c'*64})
    def test_manifest_path_traversal(self):
        with self.assertRaises(ManifestError):verify_manifest(replace(manifest(),artifacts=(ArtifactDigest('../secret','b'*64),)),{'../secret':'b'*64})
    def test_live_gate_defaults_closed(self):
        with self.assertRaises(GuardError):assert_live_release_gate(ExecutionGate(False,False,False,False,False,False))

if __name__=='__main__':unittest.main()
