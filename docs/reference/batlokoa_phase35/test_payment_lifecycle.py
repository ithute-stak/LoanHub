"""Offline lifecycle contract checks; no provider or database access."""
from decimal import Decimal
import unittest
from payment_lifecycle import Lifecycle, State, Event, InvalidTransition, apply_event

def advance(state, event, **opts):
    return apply_event(state, event, expected_sequence=state.sequence, **opts)

class LifecycleContractTests(unittest.TestCase):
    def submitted(self):
        state = Lifecycle(State.RESERVED, Decimal("125.50"))
        state = advance(state, Event.REQUIRE_AUTHORIZATION)
        state = advance(state, Event.AUTHORIZE, approved_mandate=True)
        return advance(state, Event.SUBMIT)

    def test_requires_mandate(self):
        state = advance(Lifecycle(State.RESERVED, Decimal("125.50")),
                        Event.REQUIRE_AUTHORIZATION)
        with self.assertRaises(InvalidTransition):
            advance(state, Event.AUTHORIZE)

    def test_unknown_must_not_resubmit(self):
        unknown = advance(self.submitted(), Event.PROVIDER_TIMEOUT)
        with self.assertRaises(InvalidTransition):
            advance(unknown, Event.SUBMIT)

    def test_authenticated_settlement(self):
        settled = advance(self.submitted(), Event.CONFIRM_SETTLEMENT,
            settlement_amount=Decimal("125.50"), authenticated_provider_evidence=True)
        self.assertEqual(settled.state, State.SETTLED)
        with self.assertRaises(InvalidTransition):
            advance(settled, Event.CONFIRM_SETTLEMENT,
                settlement_amount=Decimal("125.50"), authenticated_provider_evidence=True)

    def test_rejects_partial_settlement(self):
        with self.assertRaises(InvalidTransition):
            advance(self.submitted(), Event.CONFIRM_SETTLEMENT,
                settlement_amount=Decimal("100.00"), authenticated_provider_evidence=True)

    def test_rejects_missing_evidence(self):
        with self.assertRaises(InvalidTransition):
            advance(self.submitted(), Event.CONFIRM_SETTLEMENT,
                settlement_amount=Decimal("125.50"))

    def test_rejects_stale_sequence(self):
        with self.assertRaises(InvalidTransition):
            apply_event(self.submitted(), Event.PROVIDER_TIMEOUT, expected_sequence=0)

    def test_reversal_requires_approval(self):
        settled = advance(self.submitted(), Event.CONFIRM_SETTLEMENT,
            settlement_amount=Decimal("125.50"), authenticated_provider_evidence=True)
        with self.assertRaises(InvalidTransition):
            advance(settled, Event.REQUEST_REVERSAL)
        pending = advance(settled, Event.REQUEST_REVERSAL, approved_reversal=True)
        with self.assertRaises(InvalidTransition):
            advance(pending, Event.CONFIRM_REVERSAL, reversal_amount=Decimal("125.50"))
        done = advance(pending, Event.CONFIRM_REVERSAL, reversal_amount=Decimal("125.50"),
            authenticated_provider_evidence=True)
        self.assertEqual(done.state, State.REVERSED)

if __name__ == "__main__":
    unittest.main()
