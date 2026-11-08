#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEMP="$(mktemp -d)"
trap 'rm -rf "$TEMP"' EXIT
cp "$ROOT/payload/services/wacom-connector/loanhub_document_intents.go" "$TEMP/"
cp "$ROOT/payload/services/wacom-connector/wacom_local_authority.go" "$TEMP/"
cp "$ROOT/payload/services/wacom-connector/loanhub_pc_document_ui.go" "$TEMP/"
cp "$ROOT/payload/services/wacom-connector/wacom_offline_flow_test.go" "$TEMP/"
cp "$ROOT/tools/go_offline_harness/loanhub_stub_test.go" "$TEMP/"
cd "$TEMP"
GO111MODULE=off go test -v ./...
