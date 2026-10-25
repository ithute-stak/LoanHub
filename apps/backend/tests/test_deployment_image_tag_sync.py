"""Production image-tag synchronization must preserve the environment file."""
from pathlib import Path
import os
import subprocess
import sys


SCRIPT = Path(__file__).resolve().parents[3] / "scripts/deploy-production-manual.sh"


def _sync(tmp_path, initial, release):
    (tmp_path / ".env.production").write_text(initial)
    script = SCRIPT.read_text()
    python_body = script.split("sync_production_image_tag() {", 1)[1].split("<<'PY'\n", 1)[1].split("\nPY", 1)[0]
    env = {**os.environ, "LOANHUB_SYNC_IMAGE_RELEASE": release}
    subprocess.run([sys.executable, "-c", python_body], cwd=tmp_path, env=env, check=True)
    return (tmp_path / ".env.production").read_text()


def test_stored_image_tag_updated_without_changing_other_settings(tmp_path):
    result = _sync(tmp_path, "DB_NAME=loanhub\nLOANHUB_IMAGE_TAG=" + "a" * 40 + "\nDB_USER=loanhub\n", "b" * 40)
    assert result == "DB_NAME=loanhub\nLOANHUB_IMAGE_TAG=" + "b" * 40 + "\nDB_USER=loanhub\n"
    assert ((tmp_path / ".env.production").stat().st_mode & 0o777) == 0o600


def test_stored_image_tag_added_if_missing(tmp_path):
    result = _sync(tmp_path, "DB_NAME=loanhub", "c" * 40)
    assert result == "DB_NAME=loanhub\nLOANHUB_IMAGE_TAG=" + "c" * 40 + "\n"


def test_duplicate_image_tags_are_collapsed(tmp_path):
    result = _sync(tmp_path, "LOANHUB_IMAGE_TAG=old\nDB_NAME=loanhub\nLOANHUB_IMAGE_TAG=older\n", "d" * 40)
    assert result == "LOANHUB_IMAGE_TAG=" + "d" * 40 + "\nDB_NAME=loanhub\n"


def test_script_wires_tag_to_release_and_rollback():
    text = SCRIPT.read_text()
    assert 'sync_production_image_tag "$RELEASE_SHA"' in text
    assert 'sync_production_image_tag "$rollback_release"' in text
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
