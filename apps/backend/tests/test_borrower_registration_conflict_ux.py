from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROUTE = ROOT / "apps/backend/routers/borrower_registration.py"
BORROWER_SLICE = ROOT / "apps/frontend/store/features/slices/borrowerSlice.ts"
REGISTRATION_PAGE = ROOT / "apps/frontend/app/(visitors)/borrower-registration/page.tsx"


def test_registration_normalizes_phone_before_duplicate_check_and_create() -> None:
    source = BACKEND_ROUTE.read_text(encoding="utf-8")

    assert "phone = payload.phone.strip()" in source
    assert "User.phone == phone" in source
    assert "phone=phone" in source
    assert "User.phone == payload.phone" not in source


def test_duplicate_registration_messages_explain_existing_account_recovery() -> None:
    source = BACKEND_ROUTE.read_text(encoding="utf-8")

    assert "This phone number is already registered." in source
    assert "This email address is already registered." in source
    assert "already linked to a" in source
    assert "LoanHub borrower profile" in source
    assert source.count("Forgot password") >= 3
    assert "Do not create a second profile" in source


def test_create_borrower_request_sets_loading_and_error_state() -> None:
    source = BORROWER_SLICE.read_text(encoding="utf-8")

    assert "createBorrower.pending" in source
    assert "createBorrower.fulfilled" in source
    assert "createBorrower.rejected" in source
    assert "state.loading=true" in source
    assert "state.loading=false" in source
    assert "state.error=" in source
    assert "action.payload ??" in source


def test_registration_page_guides_existing_borrowers_to_account_access() -> None:
    source = REGISTRATION_PAGE.read_text(encoding="utf-8")

    assert 'href="/login"' in source
    assert 'href="/forgot-password"' in source
    assert "Already have a LoanHub borrower account?" in source
    assert "Sign in" in source
    assert "Forgot password" in source
