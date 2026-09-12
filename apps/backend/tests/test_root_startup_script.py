from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
START_SCRIPT = ROOT / "start.sh"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def test_startup_script_uses_next_cli_without_literal_double_dash() -> None:
    source = START_SCRIPT.read_text(encoding="utf-8")

    assert 'exec "${PNPM_CMD[@]}" exec next dev' in source
    assert "dev -- --hostname" not in source


def test_startup_script_applies_alembic_head_by_default() -> None:
    source = START_SCRIPT.read_text(encoding="utf-8")

    assert 'RUN_MIGRATIONS="${LOANHUB_RUN_MIGRATIONS:-1}"' in source
    assert '"$PYTHON_BIN" -m alembic upgrade head' in source
    assert "run_database_migrations" in source


def test_frontend_runtime_command_passes_hostname_and_port_as_next_options(tmp_path: Path) -> None:
    root = tmp_path / "LoanHub"
    backend = root / "apps" / "backend"
    frontend = root / "apps" / "frontend"
    fakebin = root / "fakebin"
    backend.mkdir(parents=True)
    frontend.mkdir(parents=True)
    fakebin.mkdir(parents=True)

    shutil.copy2(START_SCRIPT, root / "start.sh")
    (root / "start.sh").chmod(0o755)
    (backend / "main.py").write_text("app = object()\n", encoding="utf-8")
    (backend / "requirements.txt").write_text("", encoding="utf-8")
    (frontend / "package.json").write_text('{"scripts":{"dev":"next dev"}}\n', encoding="utf-8")
    (frontend / "node_modules").mkdir()

    python_log = root / "python.log"
    pnpm_log = root / "pnpm.log"
    event_log = root / "events.log"

    _write_executable(
        fakebin / "python3",
        "#!/usr/bin/env bash\n"
        'if [[ "${1:-}" == "-c" ]]; then exit 0; fi\n'
        'if [[ "$*" == "-m alembic upgrade head" ]]; then\n'
        '  printf "migration:%s\\n" "$*" >> "$EVENT_LOG"\n'
        '  exit 0\n'
        'fi\n'
        'printf "backend:%s\\n" "$*" >> "$EVENT_LOG"\n'
        'printf "%s\\n" "$*" > "$PYTHON_LOG"\n'
        'trap "exit 0" TERM INT\n'
        "while true; do sleep 0.1; done\n",
    )
    _write_executable(fakebin / "node", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(
        fakebin / "pnpm",
        "#!/usr/bin/env bash\n"
        'printf "frontend:%s\\n" "$*" >> "$EVENT_LOG"\n'
        'printf "%s\\n" "$*" > "$PNPM_LOG"\n'
        "exit 0\n",
    )
    _write_executable(fakebin / "ss", "#!/usr/bin/env bash\nexit 0\n")

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fakebin}:/usr/bin:/bin",
            "PYTHON_LOG": str(python_log),
            "PNPM_LOG": str(pnpm_log),
            "EVENT_LOG": str(event_log),
            "BACKEND_PORT": "8123",
            "FRONTEND_PORT": "3456",
            "LOANHUB_AUTO_INSTALL": "0",
        }
    )

    result = subprocess.run(
        [str(root / "start.sh")],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        timeout=5,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert pnpm_log.read_text(encoding="utf-8").strip() == (
        "exec next dev --hostname 0.0.0.0 --port 3456"
    )
    backend_args = python_log.read_text(encoding="utf-8")
    assert "-m uvicorn main:app" in backend_args
    assert "--port 8123" in backend_args

    events = event_log.read_text(encoding="utf-8").splitlines()
    assert events[0] == "migration:-m alembic upgrade head"
    assert any(line.startswith("backend:-m uvicorn main:app") for line in events[1:])
    assert any(line.startswith("frontend:exec next dev") for line in events[1:])
