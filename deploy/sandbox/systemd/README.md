# Sandbox reset scheduling

Do not install or enable the timer until the independent sandbox has passed runtime isolation, full reset and login tests. The proposed checkout path is /opt/loanhub-sandbox, never /opt/loanhub.

Use a root-controlled checkout and environment file (mode 0600). Docker access is privileged. The service requires the explicit .reset-approved marker in the sandbox directory; create it only after successful manual certification. Keep the marker outside version control.

Before enabling, verify the units using systemd-analyze verify and verify the calendar with systemd-analyze calendar '*-*-* 00:00:00 Africa/Maseru'. Install both units in /etc/systemd/system, reload systemd, then enable --now loanhub-sandbox-reset.timer. Verify the next run using systemctl list-timers loanhub-sandbox-reset.timer.

The timer is intentionally non-persistent so a missed midnight does not cause an unexpected destructive reset at host startup. A failed reset requires operator investigation; do not point the service at production or use broad Docker cleanup commands.

Disable with systemctl disable --now loanhub-sandbox-reset.timer. Remove the approval marker to prevent subsequent scheduled runs. The sandbox is shared; all visitor changes and uploaded demo documents are disposable. No real customer data should be entered.
