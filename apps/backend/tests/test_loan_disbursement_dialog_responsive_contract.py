"""Keep the loan disbursement confirmation responsive without relaxing integrity guards."""
from pathlib import Path


def test_disbursement_dialog_is_spacious_and_responsive():
    frontend = Path(__file__).parents[2] / "frontend" / "app" / "(dashboard)" / "company" / "loans" / "page.tsx"
    source = frontend.read_text(encoding="utf-8")
    dialog = source.split('<CustomDialog open={disburseOpen}')[1] if '<CustomDialog open={disburseOpen}' in source else source.split('open={disburseOpen}')[1]
    dialog = dialog.split('</CustomDialog>')[0]
    assert 'sm:max-w-3xl lg:max-w-5xl xl:max-w-6xl' in dialog
    assert 'max-h-[calc(100dvh-1.5rem)]' in dialog
    assert 'lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]' in dialog
    assert 'aria-label="Loan summary and disbursement controls"' in dialog
    assert 'aria-label="Disbursement payment details"' in dialog
    assert 'sticky bottom-0' in dialog
    assert 'PaymentMethodFields' in dialog
    assert 'showGatewayRailPicker={false}' in dialog
    assert 'disbursementIntegrity.passed' in dialog
    assert 'ownerOverrideEligible' in dialog
    assert 'onClick={() => void disburse()}' in dialog
    assert 'loading={disbursing || integrityLoading}' in dialog
