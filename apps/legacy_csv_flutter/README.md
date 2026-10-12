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
