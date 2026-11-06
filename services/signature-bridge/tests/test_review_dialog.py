"""UI-independent safety tests for the staging signing-review dialog."""
import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import review_dialog
import install_review_autostart


class ReviewDialogSafetyTests(unittest.TestCase):
    def setUp(self):
        self.mode = patch.dict(os.environ, {"LOANHUB_SIGNATURE_BRIDGE_MODE": "staging"})
        self.mode.start()

    def tearDown(self):
        self.mode.stop()

    def test_capture_refuses_production_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            p = Path(temporary) / "adapter"
            p.write_text("#!/bin/sh\n")
            p.chmod(0o700)
            with patch.dict(os.environ, {"LOANHUB_SIGNATURE_BRIDGE_MODE": "production"}), \
                 patch.object(review_dialog.subprocess, "run") as process:
                with self.assertRaisesRegex(ValueError, "requires staging"):
                    review_dialog.capture_once(p)
            process.assert_not_called()

    def test_national_id_syntax_is_only_input_hygiene(self):
        self.assertEqual(review_dialog.validate_national_id(" A12345-67 "), "A12345-67")
        for candidate in ("", "abc", "  ", "id with spaces", "a" * 33, "x\nsecret"):
            with self.subTest(value=candidate):
                with self.assertRaises(ValueError):
                    review_dialog.validate_national_id(candidate)

    def test_adapter_permissions_must_be_private(self):
        with tempfile.TemporaryDirectory() as temporary:
            p = Path(temporary) / "adapter"
            p.write_text("#!/bin/sh\n")
            p.chmod(0o700)
            self.assertTrue(review_dialog.adapter_is_trusted(p))
            p.chmod(0o777)
            self.assertFalse(review_dialog.adapter_is_trusted(p))

    def test_capture_refuses_noninteractive_session_before_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            p = Path(temporary) / "adapter"
            p.write_text("#!/bin/sh\n")
            p.chmod(0o700)
            with patch.object(review_dialog.sys.stdin, "isatty", return_value=False), \
                 patch.object(review_dialog.subprocess, "run") as process:
                with self.assertRaisesRegex(ValueError, "interactive terminal"):
                    review_dialog.capture_once(p)
            process.assert_not_called()

    def test_watch_reports_only_redacted_contact_signal(self):
        with tempfile.TemporaryDirectory() as temporary:
            adapter = Path(temporary) / "adapter"
            adapter.write_text("#!/bin/sh\n")
            adapter.chmod(0o700)
            result = type("Result", (), {"returncode": 0, "stdout": b"pen-contact\\n"})()
            with patch.object(review_dialog.sys.stdin, "isatty", return_value=True), \\
                 patch.object(review_dialog.subprocess, "run", return_value=result) as launch:
                self.assertTrue(review_dialog.watch_first_pen_contact(adapter))
            self.assertEqual(launch.call_args.args[0][1], "--watch-pen-contact")
            self.assertEqual(launch.call_args.kwargs["stderr"], review_dialog.subprocess.DEVNULL)

    def test_watch_does_not_run_in_production(self):
        with patch.dict(os.environ, {"LOANHUB_SIGNATURE_BRIDGE_MODE": "production"}), \
             patch.object(review_dialog.subprocess, "run") as launch:
            with self.assertRaisesRegex(ValueError, "requires staging"):
                review_dialog.watch_first_pen_contact(Path("/tmp/adapter"))
        launch.assert_not_called()

    def test_gnome_autostart_entry_is_staging_only_and_has_no_network(self):
        entry = install_review_autostart.build_entry(
            Path("/home/operator/bridge/review_dialog.py"),
            Path("/home/operator/go/loanhub-wacom-connector"),
            Path("/usr/bin/gnome-terminal"),
            Path("/usr/bin/python3"),
        )
        self.assertIn("--auto-watch", entry)
        self.assertIn("LOANHUB_SIGNATURE_BRIDGE_MODE=staging", entry)
        self.assertNotIn("sync", entry)
        self.assertNotIn("https://", entry)
        with self.assertRaises(ValueError):
            install_review_autostart.build_entry(
                Path("/tmp/unsafe path/review.py"), Path("/tmp/adapter"),
                Path("/usr/bin/gnome-terminal"), Path("/usr/bin/python3")
            )

    def test_capture_validates_adapter_json_without_logging_strokes(self):
        with tempfile.TemporaryDirectory() as temporary:
            p = Path(temporary) / "adapter"
            p.write_text("#!/bin/sh\n")
            p.chmod(0o700)
            raw = b'{"format":"loanhub-pen-strokes-v1","strokes":[[{"x":0.1,"y":0.1,"pressure":0.4,"t":1},{"x":0.2,"y":0.2,"pressure":0.5,"t":2}]]}'
            def fake_run(*args, **kwargs):
                kwargs["stdout"].write(raw)
                self.assertEqual(args[0][1], "--capture-strokes-json-fast")
                self.assertEqual(kwargs["cwd"], str(p.parent))
                self.assertEqual(kwargs["env"]["LOANHUB_SIGNATURE_BRIDGE_MODE"], "staging")
                self.assertEqual(kwargs["stderr"], review_dialog.subprocess.DEVNULL)
            with patch.object(review_dialog.sys.stdin, "isatty", return_value=True), \
                 patch.object(review_dialog.subprocess, "run", side_effect=fake_run):
                returned = review_dialog.capture_once(p)
            self.assertIn(b"loanhub-pen-strokes-v1", returned)


if __name__ == "__main__":
    unittest.main()
