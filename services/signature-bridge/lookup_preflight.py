"""Offline-only staging National ID lookup configuration preflight.

Never execute token helpers, contact an API, print IDs/tokens, or modify config.
This establishes local file/URL validity only, not remote authorization.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from client_lookup import load_lookup_config


def assess(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "Lookup profile is missing; remote client lookup remains disabled"
    try:
        config = load_lookup_config(path)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        # Never print potentially sensitive invalid file content or exception strings.
        return False, "Lookup profile invalid or unsafe; remote client lookup remains disabled"
    # Do not print sensitive company identifiers or private helper paths.
    return True, "Local staging profile passed metadata checks; remote endpoint and credentials NOT verified"


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline-only LoanHub staging lookup preflight")
    parser.add_argument("--lookup-config", type=Path, default=Path.home() / ".config/loanhub-signature-bridge/lookup.json")
    args = parser.parse_args()
    ok, message = assess(args.lookup_config)
    print(message)
    print("No network call, token execution, signing, capture or VPS upload was attempted.")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
