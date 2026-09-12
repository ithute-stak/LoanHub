from __future__ import annotations

import json
import os
import socket
from pathlib import Path
from typing import Any


DEFAULT_SOCKET_PATH = "/run/loanhub-updater/control.sock"
MAX_RESPONSE_BYTES = 1_048_576


class SystemUpdaterError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 503):
        super().__init__(message)
        self.status_code = status_code


def _socket_path() -> str:
    return os.getenv("LOANHUB_UPDATER_SOCKET", DEFAULT_SOCKET_PATH).strip() or DEFAULT_SOCKET_PATH


def _token() -> str:
    return os.getenv("LOANHUB_UPDATER_TOKEN", "").strip()


def _unavailable(message: str) -> dict[str, Any]:
    return {
        "configured": False,
        "state": "unavailable",
        "message": message,
        "steps": [],
        "details": {},
    }


def request_updater(command: str) -> dict[str, Any]:
    if command not in {"status", "update"}:
        raise ValueError("Unsupported updater command")

    socket_path = _socket_path()
    token = _token()

    if not token:
        if command == "status":
            return _unavailable("Host updater token is not configured in the LoanHub container")
        raise SystemUpdaterError("Host updater token is not configured")

    if not Path(socket_path).exists():
        if command == "status":
            return _unavailable("Host updater service is not available")
        raise SystemUpdaterError("Host updater service is not available")

    payload = json.dumps({"command": command, "token": token}, separators=(",", ":")).encode("utf-8") + b"\n"

    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(5.0)
            client.connect(socket_path)
            client.sendall(payload)

            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = client.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > MAX_RESPONSE_BYTES:
                    raise SystemUpdaterError("Host updater returned an oversized response", status_code=502)
                if b"\n" in chunk:
                    break
    except (OSError, TimeoutError) as error:
        if command == "status":
            return _unavailable(f"Host updater connection failed: {error}")
        raise SystemUpdaterError("Could not connect to the host updater") from error

    raw = b"".join(chunks).split(b"\n", 1)[0]
    if not raw:
        raise SystemUpdaterError("Host updater returned an empty response", status_code=502)

    try:
        response = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SystemUpdaterError("Host updater returned invalid JSON", status_code=502) from error

    if not isinstance(response, dict):
        raise SystemUpdaterError("Host updater returned an invalid response", status_code=502)

    if not response.get("ok", False):
        status_code = int(response.get("status_code") or 503)
        raise SystemUpdaterError(str(response.get("error") or "Host updater rejected the request"), status_code=status_code)

    status = response.get("status")
    if not isinstance(status, dict):
        raise SystemUpdaterError("Host updater response did not contain status information", status_code=502)

    status["configured"] = True
    return status


def get_system_update_status() -> dict[str, Any]:
    return request_updater("status")


def trigger_system_update() -> dict[str, Any]:
    return request_updater("update")
