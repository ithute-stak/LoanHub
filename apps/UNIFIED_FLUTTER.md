# Unified LoanHub Flutter app

The sole active Flutter application source is `apps/call_mobile`.

It retains the LoanHub Call Mobile theme, navigation, calls, chats and money features and includes legacy bank deduction capture, record management, CSV/XLSX import, and bank export under `lib/features/legacy/`.

Use `.github/workflows/unified-flutter.yml` to validate and build the app. The old standalone `apps/legacy_csv_flutter` application and `.github/workflows/legacy-flutter.yml` were retired on this branch, and remain recoverable through Git history.

Do not release until analyzer, formatting, unit/widget tests, APK build, finance role authorisation, authentication refresh, tenant switching, real-device import and bank export validation pass. Changes here are not proof of deployment readiness.
