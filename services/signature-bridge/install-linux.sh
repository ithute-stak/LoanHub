#!/usr/bin/env bash
# Install as an unprivileged per-user service; starts at login or after boot
# if the operator explicitly enables systemd linger for this desktop user.
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${EUID}" == 0 ]]; then
  echo "Run as the desktop account, not root." >&2
  exit 1
fi
PYTHON="${APP_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON}" ]]; then
  echo "Create .venv first: python3 -m venv .venv && .venv/bin/pip install cryptography" >&2
  exit 1
fi
"${PYTHON}" -c 'import cryptography'
mkdir -p "${HOME}/.config/systemd/user" "${HOME}/.local/share/loanhub-signature-bridge"
chmod 700 "${HOME}/.local/share/loanhub-signature-bridge"
cat > "${HOME}/.config/systemd/user/loanhub-signature-bridge.service" <<EOF
[Unit]
Description=LoanHub Signature Bridge offline vault
After=default.target
[Service]
Type=simple
ExecStart=${PYTHON} ${APP_DIR}/bridge.py serve
Restart=on-failure
RestartSec=5
UMask=0077
NoNewPrivileges=true
[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now loanhub-signature-bridge.service
echo "Installed and started for this user."
echo "To run after boot before login: sudo loginctl enable-linger ${USER}"
echo "Verify: systemctl --user status loanhub-signature-bridge.service"
