#!/usr/bin/env bash
# Install as an unprivileged per-user service; starts on login and after reboot
# only when linger is explicitly enabled.
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${EUID}" == 0 ]]; then
  echo "Run as the desktop account, not root." >&2
  exit 1
fi
command -v python3 >/dev/null
python3 -c 'import cryptography' || { echo "Install cryptography into your user virtual environment first." >&2; exit 1; }
mkdir -p "${HOME}/.config/systemd/user"
chmod 700 "${HOME}/.config/systemd"
cat > "${HOME}/.config/systemd/user/loanhub-signature-bridge.service" <<EOF
[Unit]
Description=LoanHub Signature Bridge offline vault
After=default.target
[Service]
Type=simple
ExecStart=/usr/bin/env python3 ${APP_DIR}/bridge.py serve
Restart=on-failure
RestartSec=5
UMask=0077
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=%h/.local/share/loanhub-signature-bridge
[Install]
WantedBy=default.target
EOF
mkdir -p "${HOME}/.local/share/loanhub-signature-bridge"
chmod 700 "${HOME}/.local/share/loanhub-signature-bridge"
systemctl --user daemon-reload
systemctl --user enable --now loanhub-signature-bridge.service
echo "Installed and started for this user. To start even before login after reboot:"
echo "  sudo loginctl enable-linger ${USER}"
echo "Verify: systemctl --user status loanhub-signature-bridge.service"
