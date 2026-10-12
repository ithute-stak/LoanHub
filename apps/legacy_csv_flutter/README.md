# LoanHub Legacy CSV — Flutter capture

Mobile-friendly Flutter UI for transcribing historical bank deductions into LoanHub.
This is **not** a new loan origination screen or a transaction posting engine.

## Run

Install Flutter 3.24+ and run from this directory:

```bash
flutter create --platforms=android,ios,web .
flutter pub get
flutter run --dart-define=LOANHUB_API_URL=https://YOUR-LOANHUB-HOST/api/v1
```

The company-scoped backend requires an existing LoanHub access token with a
company finance or management role. The initial connection screen accepts the
token and company UUID; credentials are held in Flutter secure storage.
For production, replace manual token entry with LoanHub's central OAuth/OIDC
PKCE sign-in flow, secure session refresh, and token revocation.

## Capture

Work group is populated from `/legacy-bank-deductions/work-groups`.
Enter client name, account number (digits), branch code (up to six digits),
and deduction amount (LSL). The API saves full account numbers encrypted,
pads branch codes to six digits, and returns a masked CSV-like register.

The backend migration must be applied before use. The **Export bank CSV ZIP** button requests an archive generated on the backend
from this manual historical register only. FNB has a single file combining all
three work groups; STD, LPS and NB are separated by work group. This export
is separate from live outstanding-loan exports. Invalid work-group or account
records are excluded by the exporter, so review saved data carefully.

On Android and iOS the ZIP is shared using the operating system share sheet.
The initial Flutter app is **mobile-first**; web download handling and full
Flutter build testing remain outstanding.

Never commit authentication tokens or real bank data to Git.

## Bulk CSV import

Select **Import CSV**, review the validation summary, then confirm saving.
CSV must be UTF-8, at most 2 MB and 5,000 rows. The first header row
is optional. The columns must be in exactly this order:

```csv
Work group,Client name,Account number,Branch code,Amount
Force,Example Client,6200123456,000123,450.00
Civil,Another Client,9001234567,070,600.00
S/E,Third Client,1001234567,000010,250.00
```

Import the account number and branch code as **text** in any spreadsheet
editor; otherwise leading zeros may disappear. Work groups must already
exist in LoanHub's active employer-group API. The server checks all rows,
rejects duplicates and invalid entries, and refuses to save a file if
any row is invalid. Nothing is posted to financial ledgers.

## Sign-in and recovery

Sign in using the existing LoanHub phone number, password, and optional MFA
one-time code. Choose your company UUID for tenant routing. The app stores
only the returned bearer token with secure storage; passwords are not
persisted. Sign out clears local credentials. Refresh-token rotation and
company selection by name are still planned.

Company managers may open **Restore** to recover previously soft-deleted
legacy records. Other finance roles cannot list or restore deleted records.
