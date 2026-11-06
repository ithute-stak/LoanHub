#!/usr/bin/env python3
"""Install or remove a GNOME graphical-session startup entry for test-only review.

The Wacom vendor SDK requires an interactive controlling TTY: Ptyxis or
GNOME Terminal provides one. This cannot display a GUI before the user logs into GNOME.
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import sys

ENTRY_NAME = "loanhub-staging-signature-review.desktop"
SAFE_PATH = re.compile(r"^/[A-Za-z0-9_./-]+$")


def build_entry(script: Path, adapter: Path, terminal: Path, python: Path, lookup_config: Path | None = None) -> str:
    for path in (script, adapter, terminal, python, *([lookup_config] if lookup_config else [])):
        if not SAFE_PATH.fullmatch(str(path)):
            raise ValueError("Autostart paths must be absolute and contain no spaces or shell characters")
    if terminal.name not in ("ptyxis", "gnome-terminal"):
        raise ValueError("Supported terminal must be Ptyxis or GNOME Terminal")
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=LoanHub STU-540 Review (Staging)\n"
        "Comment=Listen locally for the first Wacom pen contact after GNOME login\n"
        f"Exec={terminal} -- /usr/bin/env LOANHUB_SIGNATURE_BRIDGE_MODE=staging "
        f"{python} {script} --sdk-adapter {adapter} --auto-watch"
        f"{' --lookup-config ' + str(lookup_config) if lookup_config else ''}\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
        "StartupNotify=false\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--install", action="store_true")
    action.add_argument("--remove", action="store_true")
    args = parser.parse_args()
    target = Path.home() / ".config" / "autostart" / ENTRY_NAME
    if args.remove:
        target.unlink(missing_ok=True)
        print("Removed LoanHub staging autostart entry.")
        return 0
    terminal = shutil.which("ptyxis") or shutil.which("gnome-terminal")
    if not terminal:
        print("Ptyxis or GNOME Terminal is required for the vendor Wacom SDK's real TTY. Autostart not installed.", file=sys.stderr)
        return 1
    script = Path(__file__).resolve().parent / "review_dialog.py"
    python = Path(sys.executable).resolve()
    adapter = script.parent.parent / "wacom-connector" / "loanhub-wacom-connector"
    if not script.is_file() or not adapter.is_file():
        print("Review dialog or Go adapter is missing; autostart not installed.", file=sys.stderr)
        return 1
    lookup_config = Path.home() / ".config" / "loanhub-signature-bridge" / "lookup.json"
    if lookup_config.exists():
        from client_lookup import load_lookup_config
        load_lookup_config(lookup_config)
    else:
        lookup_config = None
    text = build_entry(script, adapter, Path(terminal), python, lookup_config)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(target.parent, 0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW
    fd = os.open(target, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        output.write(text)
    os.chmod(target, 0o600)
    print("Installed GNOME session autostart:", target)
    print("Starts after graphical login, not before login. Opens", Path(terminal).name, "for SDK TTY support.")
    print("National ID lookup profile:", "configured" if lookup_config else "missing; real client lookup disabled")
    print("Pen watcher stays active after desktop login; no VPS signature upload enabled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
