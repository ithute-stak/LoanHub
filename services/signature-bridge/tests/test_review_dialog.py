"""UI-independent safety tests for the staging signing-review dialog."""
import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import review_dialog


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

    def test_capture_validates_adapter_json_without_logging_strokes(self):
        with tempfile.TemporaryDirectory() as temporary:
            p = Path(temporary) / "adapter"
            p.write_text("#!/bin/sh\n")
            p.chmod(0o700)
            raw = b'{"format":"loanhub-pen-strokes-v1","strokes":[[{"x":0.1,"y":0.1,"pressure":0.4,"t":1},{"x":0.2,"y":0.2,"pressure":0.5,"t":2}]]}'
            def fake_run(*args, **kwargs):
                kwargs["stdout"].write(raw)
                self.assertEqual(kwargs["cwd"], str(p.parent))
                self.assertEqual(kwargs["env"]["LOANHUB_SIGNATURE_BRIDGE_MODE"], "staging")
                self.assertEqual(kwargs["stderr"], review_dialog.subprocess.DEVNULL)
            with patch.object(review_dialog.sys.stdin, "isatty", return_value=True), \
                 patch.object(review_dialog.subprocess, "run", side_effect=fake_run):
                returned = review_dialog.capture_once(p)
            self.assertIn(b"loanhub-pen-strokes-v1", returned)


if __name__ == "__main__":
    unittest.main()
