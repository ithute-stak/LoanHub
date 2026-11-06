#!/usr/bin/env bash
# Run ONLY on the Linux PC with the physical Wacom STU-540.
# Safe by default: no credentials, signatures, network calls or file uploads.
set -Eeuo pipefail
umask 077

usage() {
  cat <<'HELP'
LoanHub Wacom physical workstation readiness

Usage:
  bash scripts/workstation_readiness.sh
  bash scripts/workstation_readiness.sh --hardware

Default:
  Checks local Go source/tests, Wacom SDK executable paths and USB identity.
  No pen captures and no LoanHub network calls.

--hardware:
  Explicitly runs the existing disposable STU-540 pen-to-PNG test using
  official SDK tools. Draw only meaningless TEST scribbles.
  It does NOT create signature files or upload to LoanHub.

Environment:
  WACOM_SDK_QUERY=/absolute/path/to/query
  WACOM_SDK_PEN_SAMPLE=/absolute/path/to/simpleInterface

Do NOT run as root or on the production VPS.
HELP
}

hardware=0
case "${1:-}" in
  "") ;;
  --hardware) hardware=1 ;;
  -h|--help) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac
[[ $# -le 1 ]] || { usage >&2; exit 2; }

if [[ ${EUID} -eq 0 ]]; then
  echo "FAIL: run as the ordinary desktop user, not root" >&2
  exit 1
fi
if [[ "$(uname -s)" != "Linux" ]]; then
  echo "FAIL: this test requires the Linux workstation" >&2
  exit 1
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
connector_dir="$(cd -- "${script_dir}/.." && pwd)"
cd "${connector_dir}"
if [[ ! -f go.mod || ! -f main.go ]]; then
  echo "FAIL: cannot locate the local Wacom Go connector" >&2
  exit 1
fi

echo "== Step 1: Local Go unit and integration tests =="
command -v go >/dev/null || { echo "FAIL: Go is not installed" >&2; exit 1; }
go version
go test ./...

echo "== Step 2: Wacom SDK executable checks =="
sdk_root="${HOME}/wacom-stu-sdk/sdk-extracted/Linux/x86_64"
query="${WACOM_SDK_QUERY:-${sdk_root}/query}"
pen="${WACOM_SDK_PEN_SAMPLE:-${sdk_root}/simpleInterface}"
for path in "${query}" "${pen}"; do
  if [[ "${path}" != /* || ! -f "${path}" || ! -x "${path}" || -L "${path}" ]]; then
    echo "FAIL: missing/non-executable or symbolic-link SDK tool at configured path" >&2
    exit 1
  fi
done
command -v script >/dev/null || { echo "FAIL: util-linux script utility missing" >&2; exit 1; }

echo "== Step 3: Local STU-540 USB identity =="
device_found=0
shopt -s nullglob
for device in /sys/bus/usb/devices/*; do
  [[ -f "${device}/idVendor" && -f "${device}/idProduct" ]] || continue
  IFS= read -r vendor < "${device}/idVendor" || continue
  IFS= read -r product < "${device}/idProduct" || continue
  if [[ "${vendor,,}" == "056a" && "${product,,}" == "00a8" ]]; then
    device_found=1
    break
  fi
done
if [[ "${device_found}" != 1 ]]; then
  echo "FAIL: Wacom STU-540 USB device (056a:00a8) not detected" >&2
  exit 1
fi
echo "PASS: USB identity detected; this is NOT proof of working pen capture"

echo "== Step 4: Capture mode =="
if [[ "${hardware}" == 0 ]]; then
  echo "PASS: safe readiness checks complete; no handwriting captured"
  echo "To test disposable pen strokes, run --hardware on this PC"
  exit 0
fi

if [[ ! -t 0 || ! -t 1 ]]; then
  echo "FAIL: physical hardware test requires an interactive terminal" >&2
  exit 1
fi

echo "IMPORTANT: Draw only non-identifying TEST scribbles."
echo "Never sign a contract or use a real borrower/operator signature here."
printf 'Type TEST to run the disposable hardware test: '
IFS= read -r acknowledgement
if [[ "${acknowledgement}" != "TEST" ]]; then
  echo "Cancelled: no handwriting capture started"
  exit 2
fi

echo "== Step 5: Official SDK pen-to-PNG disposable test =="
# No signature bytes are output, persisted or sent to a backend.
go run . --disposable-png-test \
  --sdk-query="${query}" \
  --sdk-pen-sample="${pen}"
echo "PASS: Wacom physical SDK diagnostic completed"
echo "RESULT: test-only capture validated; no contract signing enabled"
