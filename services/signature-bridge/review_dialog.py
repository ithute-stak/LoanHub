#!/usr/bin/env python3
"""Staging-only Wacom signing review dialog. No remote upload or customer signing.

Run from an operator terminal, which the Wacom SDK needs for pen capture.
All accepted strokes remain in volatile memory until the dialog is dismissed.
A supplied National ID is unverified and is never written to disk or logs.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import queue
import re
import stat
import subprocess
import sys
import tempfile
import threading

from capture_protocol import MAX_BYTES, validate_strokes


def validate_national_id(value: str) -> str:
    """Basic input hygiene only, NOT Lesotho identity verification."""
    candidate = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9/-]{4,32}", candidate):
        raise ValueError("Enter a National ID using 4–32 letters, digits, / or -")
    return candidate


def adapter_is_trusted(path: Path) -> bool:
    if not path.is_absolute():
        return False
    try:
        info = path.lstat()
    except OSError:
        return False
    return (stat.S_ISREG(info.st_mode) and info.st_uid in (0, os.getuid())
            and info.st_mode & 0o111 != 0 and info.st_mode & 0o022 == 0)


def capture_once(executable: Path) -> bytes:
    """Acquire private stroke JSON via verified adapter, never log raw data."""
    if not adapter_is_trusted(executable):
        raise ValueError("Wacom adapter permissions or ownership are not trusted")
    if not sys.stdin.isatty():
        raise ValueError("Launch this dialog from an interactive terminal for Wacom SDK access")
    env = {"HOME": str(Path.home()), "PATH": "/usr/bin:/bin",
           "LANG": "C.UTF-8", "TERM": "xterm",
           "LOANHUB_SIGNATURE_BRIDGE_MODE": "staging"}
    with tempfile.TemporaryFile() as output:
        try:
            subprocess.run(
                [str(executable), "--capture-strokes-json"],
                stdin=sys.stdin, stdout=output, stderr=subprocess.DEVNULL,
                cwd=str(executable.parent), env=env, timeout=35, check=True,
            )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
            raise ValueError("Capture did not finish; please restart the test") from exc
        output.seek(0)
        return validate_strokes(output.read(MAX_BYTES + 1)).canonical


class ReviewDialog:
    """Only staged preview and discard paths are enabled pending server certification."""

    def __init__(self, root, adapter: Path):
        import tkinter as tk
        from tkinter import ttk
        self.root = root
        self.adapter = adapter
        self.tk = tk
        self.ttk = ttk
        self.events = queue.Queue()
        self.capture = None
        self.busy = False
        self.generation = 0
        self.national_id = tk.StringVar()
        self.status = tk.StringVar(value="Ready for a disposable STU-540 test capture")
        root.title("LoanHub • Signature Review — STAGING")
        root.geometry("760x570")
        root.minsize(620, 480)
        root.protocol("WM_DELETE_WINDOW", self.close)

        outer = ttk.Frame(root, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Signature review", font=("Sans", 19, "bold")).pack(anchor="w")
        ttk.Label(outer, text="STAGING / TEST SIGNATURES ONLY • No VPS upload • No contract signing").pack(anchor="w", pady=(3, 14))
        ttk.Label(outer, text="Client National ID (not yet verified)").pack(anchor="w")
        self.id_field = ttk.Entry(outer, textvariable=self.national_id, show="•", width=38)
        self.id_field.pack(anchor="w", pady=(4, 3))
        ttk.Label(outer, text="The ID is for future authenticated lookup. This dialog does not save or transmit it.").pack(anchor="w", pady=(0, 10))
        self.canvas = tk.Canvas(outer, background="#ffffff", height=245, highlightbackground="#b8c1ce", highlightthickness=1)
        self.canvas.pack(fill="both", expand=True)
        ttk.Label(outer, textvariable=self.status, wraplength=680).pack(anchor="w", pady=(12, 12))
        actions = ttk.Frame(outer)
        actions.pack(fill="x")
        self.capture_button = ttk.Button(actions, text="Start signing", command=self.start)
        self.capture_button.pack(side="left", padx=(0, 7))
        self.clear_button = ttk.Button(actions, text="Clear / Restart", command=self.restart)
        self.clear_button.pack(side="left", padx=(0, 7))
        self.reject_button = ttk.Button(actions, text="Reject signature", command=self.reject)
        self.reject_button.pack(side="left", padx=(0, 7))
        self.post_button = ttk.Button(actions, text="Post to VPS (locked)", state="disabled")
        self.post_button.pack(side="right")
        ttk.Label(outer, text="Posting requires server-side National ID matching, authenticated operator, consent and tenant checks.").pack(anchor="w", pady=(12, 0))
        root.after(100, self.poll)

    def discard(self):
        self.capture = None
        self.canvas.delete("all")
        # Clear any typed National ID; the widget masks it while entered.
        self.national_id.set("")

    def start(self):
        if self.busy:
            return
        self.discard()
        self.busy = True
        self.generation += 1
        generation = self.generation
        self.capture_button.configure(state="disabled")
        self.status.set("Capture starting. Draw disposable test strokes after SDK ready (approximately 25 seconds).")
        def worker():
            try:
                data = capture_once(self.adapter)
                self.events.put((generation, True, data))
            except (OSError, ValueError) as exc:
                self.events.put((generation, False, str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            while True:
                generation, ok, data = self.events.get_nowait()
                if generation != self.generation:
                    continue
                self.busy = False
                self.capture_button.configure(state="normal")
                if ok:
                    self.capture = data
                    envelope = validate_strokes(data)
                    self.draw_preview()
                    self.status.set(f"Preview ready: {envelope.stroke_count} strokes, {envelope.point_count} points. Review, reject or restart; upload is disabled.")
                else:
                    self.discard()
                    self.status.set("Capture failed: " + data)
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(100, self.poll)

    def draw_preview(self):
        self.canvas.delete("all")
        if self.capture is None:
            return
        value = json.loads(self.capture)
        w = max(self.canvas.winfo_width(), 500)
        h = max(self.canvas.winfo_height(), 245)
        margin = 24
        for stroke in value["strokes"]:
            points = []
            for p in stroke:
                points.extend((margin + p["x"] * (w - 2 * margin),
                               margin + p["y"] * (h - 2 * margin)))
            if len(points) >= 4:
                self.canvas.create_line(*points, fill="#172e4d", width=2, smooth=True)

    def restart(self):
        if self.busy:
            # A running SDK operation cannot safely be reset from this UI.
            self.status.set("Capture in progress. Wait for capture to finish before restarting.")
            return
        self.start()

    def reject(self):
        if self.busy:
            self.status.set("Capture is still running; rejection is available after it finishes.")
            return
        self.discard()
        self.status.set("Signature rejected and preview cleared. Nothing saved or sent.")

    def close(self):
        if self.busy:
            self.status.set("Capture is still running; close after capture completes.")
            return
        self.discard()
        self.root.destroy()


def main() -> int:
    p = argparse.ArgumentParser(description="STU-540 staging review dialog")
    p.add_argument("--sdk-adapter", required=True)
    args = p.parse_args()
    if os.environ.get("LOANHUB_SIGNATURE_BRIDGE_MODE") != "staging":
        p.error("The review dialog is only available in staging mode")
    adapter = Path(args.sdk_adapter)
    if not adapter_is_trusted(adapter):
        p.error("Provide an owned, executable adapter that is not group/world-writable")
    try:
        import tkinter as tk
        root = tk.Tk()
    except (ImportError, RuntimeError, OSError) as exc:
        print("Unable to open desktop dialog; install python3-tk and use a graphical desktop", file=sys.stderr)
        return 1
    ReviewDialog(root, adapter)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
