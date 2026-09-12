from pathlib import Path

from database.models.enums import PaymentMethod, PaymentProvider


BACKEND = Path(__file__).resolve().parents[1]
FRONTEND = BACKEND.parent / "frontend"


def test_gateway_is_the_only_new_electronic_posting_boundary():
    assert PaymentMethod.LELEFAPAYGATE.value == "lelefapaygate"
    assert PaymentProvider.LELEFAPAYGATE.value == "lelefapaygate"
    source = (BACKEND / "services" / "payment_service.py").read_text()
    assert "Direct electronic handlers were retired" in source
    assert "initiate_gateway_payment" in source


def test_payment_picker_exposes_only_cash_and_gateway():
    source = (
        FRONTEND / "components" / "payments" / "payment-method-fields.tsx"
    ).read_text()
    options = source.split("DEFAULT_PAYMENT_METHOD_OPTIONS", 1)[1].split(
        "];", 1
    )[0]
    assert 'value: "cash"' in options
    assert 'value: "lelefapaygate"' in options
    assert 'value: "mpesa_wallet"' not in options
    assert 'value: "bank"' not in options


def test_login_contract_is_unchanged_by_gateway_integration():
    router = (BACKEND / "api" / "v1" / "router.py").read_text()
    auth = (BACKEND / "routers" / "auth.py").read_text()
    assert "auth.router" in router
    assert 'router = APIRouter(prefix="/auth"' in auth
    assert '@router.post("/login"' in auth
