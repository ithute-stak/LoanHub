#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

KEY_PROPERTIES="android/key.properties"
if [[ ! -f "$KEY_PROPERTIES" ]]; then
  echo "ERROR: $KEY_PROPERTIES is missing."
  echo "Copy android/key.properties.example to android/key.properties and configure your private upload keystore first."
  exit 1
fi

for key in storePassword keyPassword keyAlias storeFile; do
  if ! grep -Eq "^${key}=.+" "$KEY_PROPERTIES"; then
    echo "ERROR: $KEY_PROPERTIES is missing a non-empty ${key}= value."
    exit 1
  fi
done

if grep -Eq '=(CHANGE_ME|changeme)$' "$KEY_PROPERTIES"; then
  echo "ERROR: Replace all CHANGE_ME values in $KEY_PROPERTIES before building for Google Play."
  exit 1
fi

if [[ -z "${LOANHUB_API_URL:-}" ]]; then
  echo "ERROR: Set LOANHUB_API_URL to the public production LoanHub HTTPS server."
  echo "Example: export LOANHUB_API_URL=https://loanhub.example.com"
  exit 1
fi

if [[ ! "$LOANHUB_API_URL" =~ ^https:// ]]; then
  echo "ERROR: LOANHUB_API_URL must start with https:// for a Google Play release."
  exit 1
fi

firebase_vars=(
  LOANHUB_FIREBASE_PROJECT_ID
  LOANHUB_FIREBASE_APP_ID
  LOANHUB_FIREBASE_API_KEY
  LOANHUB_FIREBASE_MESSAGING_SENDER_ID
)
for var_name in "${firebase_vars[@]}"; do
  if [[ -z "${!var_name:-}" ]]; then
    echo "ERROR: $var_name is required for LoanHub background message/money notifications."
    exit 1
  fi
done

STORE_FILE="$(sed -n 's/^storeFile=//p' "$KEY_PROPERTIES" | tail -n1)"
if [[ -z "$STORE_FILE" ]]; then
  echo "ERROR: storeFile is empty."
  exit 1
fi

# build.gradle.kts resolves storeFile relative to android/app.
if [[ "$STORE_FILE" = /* ]]; then
  RESOLVED_STORE_FILE="$STORE_FILE"
else
  RESOLVED_STORE_FILE="$APP_DIR/android/app/$STORE_FILE"
fi

if [[ ! -f "$RESOLVED_STORE_FILE" ]]; then
  echo "ERROR: Upload keystore not found at $RESOLVED_STORE_FILE"
  exit 1
fi

flutter clean
flutter pub get
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test --timeout 30s
flutter build appbundle --release \
  --dart-define="LOANHUB_API_URL=$LOANHUB_API_URL" \
  --dart-define="LOANHUB_FIREBASE_PROJECT_ID=$LOANHUB_FIREBASE_PROJECT_ID" \
  --dart-define="LOANHUB_FIREBASE_APP_ID=$LOANHUB_FIREBASE_APP_ID" \
  --dart-define="LOANHUB_FIREBASE_API_KEY=$LOANHUB_FIREBASE_API_KEY" \
  --dart-define="LOANHUB_FIREBASE_MESSAGING_SENDER_ID=$LOANHUB_FIREBASE_MESSAGING_SENDER_ID"

BUNDLE="build/app/outputs/bundle/release/app-release.aab"
if [[ ! -s "$BUNDLE" ]]; then
  echo "ERROR: Expected App Bundle was not produced at $BUNDLE"
  exit 1
fi

printf '\nGoogle Play bundle ready:\n%s\n' "$APP_DIR/$BUNDLE"
