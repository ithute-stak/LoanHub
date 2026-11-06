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
from client_lookup import lookup_client, load_lookup_config


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
    if os.environ.get("LOANHUB_SIGNATURE_BRIDGE_MODE") != "staging":
        raise ValueError("Local review capture requires staging mode")
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
                [str(executable), "--capture-strokes-json-fast"],
                stdin=sys.stdin, stdout=output, stderr=subprocess.DEVNULL,
                cwd=str(executable.parent), env=env, timeout=35, check=True,
            )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
            raise ValueError("Capture did not finish; please restart the test") from exc
        output.seek(0)
        return validate_strokes(output.read(MAX_BYTES + 1)).canonical


def watch_first_pen_contact(executable: Path) -> bool:
    """Detect a first pen-down only, never access or return coordinates."""
    if os.environ.get("LOANHUB_SIGNATURE_BRIDGE_MODE") != "staging":
        raise ValueError("Pen watch requires staging mode")
    if not adapter_is_trusted(executable) or not sys.stdin.isatty():
        raise ValueError("Trusted adapter and interactive terminal required")
    env = {"HOME": str(Path.home()), "PATH": "/usr/bin:/bin",
           "LANG": "C.UTF-8", "TERM": "xterm",
           "LOANHUB_SIGNATURE_BRIDGE_MODE": "staging"}
    result = subprocess.run(
        [str(executable), "--watch-pen-contact"], stdin=sys.stdin,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        cwd=str(executable.parent), env=env, timeout=35, check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == b"pen-contact"


class ReviewDialog:
    """Only staged preview and discard paths are enabled pending server certification."""

    def __init__(self, root, adapter: Path, auto_watch: bool = False, lookup_config=None):
        import tkinter as tk
        from tkinter import ttk
        self.root = root
        self.adapter = adapter
        self.auto_watch = auto_watch
        self.lookup_config = lookup_config
        self.lookup_generation = 0
        self.server_match = None
        self.watching = False
        self.watch_generation = 0
        self.tk = tk
        self.ttk = ttk
        self.events = queue.Queue()
        self.capture = None
        self.busy = False
        self.generation = 0
        self.national_id = tk.StringVar()
        self.status = tk.StringVar(value="LoanHub client lookup connected; signature submission is not activated." if lookup_config else "LoanHub lookup not configured. Capture and posting disabled.")
        self.selected_national_id = None
        self.search_after = None
        root.title("LoanHub • Signature Review — STAGING")
        root.geometry("760x570")
        root.minsize(620, 480)
        root.protocol("WM_DELETE_WINDOW", self.close)

        outer = ttk.Frame(root, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Signature review", font=("Sans", 19, "bold")).pack(anchor="w")
        ttk.Label(outer, text="STAGING / TEST SIGNATURES ONLY • No VPS upload • No contract signing").pack(anchor="w", pady=(3, 14))
        ttk.Label(outer, text="Client National ID — LoanHub company lookup").pack(anchor="w")
        self.id_field = ttk.Entry(outer, textvariable=self.national_id, width=38)
        self.id_field.pack(anchor="w", pady=(4, 3))
        self.matches = tk.Listbox(outer, height=4, exportselection=False)
        self.matches.bind("<Double-Button-1>", self.choose_match)
        self.matches.bind("<Return>", self.choose_match)
        self.matches.pack(anchor="w", fill="x")
        self.matches.pack_forget()
        self.national_id.trace_add("write", self.schedule_search)
        self.id_field.bind("<Down>", self.focus_first_match)
        self.id_field.bind("<Return>", self.choose_first_match)
        self.client_info = tk.StringVar(value="Enter National ID to verify the client against authenticated LoanHub staging." if lookup_config else "Not connected: configure a private LoanHub lookup profile on this workstation.")
        ttk.Label(outer, textvariable=self.client_info, wraplength=680).pack(anchor="w", pady=(0, 10))
        self.canvas = tk.Canvas(outer, background="#ffffff", height=245, highlightbackground="#b8c1ce", highlightthickness=1)
        self.canvas.pack(fill="both", expand=True)
        ttk.Label(outer, textvariable=self.status, wraplength=680).pack(anchor="w", pady=(12, 12))
        actions = ttk.Frame(outer)
        actions.pack(fill="x")
        self.capture_button = ttk.Button(actions, text="Start signing", command=self.start)
        self.capture_button.pack(side="left", padx=(0, 7))
        self.capture_button.configure(state="disabled")
        self.clear_button = ttk.Button(actions, text="Clear / Restart", command=self.restart)
        self.clear_button.pack(side="left", padx=(0, 7))
        self.reject_button = ttk.Button(actions, text="Reject signature", command=self.reject)
        self.reject_button.pack(side="left", padx=(0, 7))
        self.post_button = ttk.Button(actions, text="Post to VPS (locked)", state="disabled")
        self.post_button.pack(side="right")
        ttk.Label(outer, text="Posting requires server-side National ID matching, authenticated operator, consent and tenant checks.").pack(anchor="w", pady=(12, 0))
        root.after(100, self.poll)
        if auto_watch:
            root.withdraw()
            root.after(250, self.start_watch)

    def schedule_search(self, *_args):
        self.selected_national_id = None
        self.server_match = None
        self.lookup_generation += 1
        if self.search_after is not None:
            self.root.after_cancel(self.search_after)
        self.search_after = self.root.after(180, self.update_matches)

    def update_matches(self):
        self.search_after = None
        if self.lookup_config:
            self.query_server_for_exact_id()
            return
        self.matches.pack_forget()
        return
    def discard(self, clear_identity: bool = True):
        self.capture = None
        self.canvas.delete("all")
        # Clearing handwriting does not erase the typed ID during recapture.
        if clear_identity:
            self.national_id.set("")
            self.selected_national_id = None
            self.matches.pack_forget()

    def start(self):
        if self.busy:
            return
        self.status.set("Real client signing blocked until verified consent and contract authorization.")
        return
        self.discard(clear_identity=False)
        self.busy = True
        self.generation += 1
        generation = self.generation
        self.capture_button.configure(state="disabled")
        self.status.set("Capture starting. Draw disposable test strokes after SDK ready (approximately 10 seconds).")
        def worker():
            try:
                data = capture_once(self.adapter)
                self.events.put(("capture", generation, True, data))
            except (OSError, ValueError) as exc:
                self.events.put(("capture", generation, False, str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def start_watch(self):
        if not self.auto_watch or self.watching or self.busy or self.root.state() != "withdrawn":
            return
        self.watching = True
        self.watch_generation += 1
        generation = self.watch_generation
        def worker():
            try:
                detected = watch_first_pen_contact(self.adapter)
            except (OSError, ValueError, subprocess.SubprocessError):
                detected = False
            self.events.put(("watch", generation, detected))
        threading.Thread(target=worker, daemon=True).start()

    def query_server_for_exact_id(self):
        self.matches.pack_forget()
        self.capture_button.configure(state="disabled")
        entered = self.national_id.get().strip()
        if not re.fullmatch(r"[A-Za-z0-9/-]{4,32}", entered):
            self.client_info.set("Enter complete National ID; no partial directory search.")
            return
        generation = self.lookup_generation
        self.client_info.set("Checking authenticated LoanHub staging records...")
        def worker():
            try:
                answer = lookup_client(
                    url=self.lookup_config["url"],
                    company_id=self.lookup_config["company_id"],
                    token_provider=self.lookup_config["token_provider"],
                    national_id=entered,
                )
                self.events.put(("lookup", generation, answer))
            except Exception:
                self.events.put(("lookup", generation, None))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "lookup":
                    _, generation, answer = event
                    if generation != self.lookup_generation:
                        continue
                    if answer is None:
                        self.client_info.set("Client lookup unavailable. Signing blocked.")
                        continue
                    state = answer["status"]
                    if state in ("existing_signature", "pending_signature_review", "matched_no_signature"):
                        match = answer["matches"][0]
                        self.server_match = match
                        self.selected_national_id = self.national_id.get().strip()
                        if state == "existing_signature":
                            message = " — SAVED SIGNATURE EXISTS. Recapture blocked; separate contract consent required for reuse."
                        elif state == "pending_signature_review":
                            message = " — SIGNATURE PENDING REVIEW. Recapture blocked."
                        else:
                            message = " — matched company borrower. Signing still requires independent authorization."
                        self.client_info.set(match["full_name"] + message)
                    else:
                        self.client_info.set("No unique authorized client match. Capture blocked.")
                    continue
                if event[0] == "watch":
                    _, generation, detected = event
                    if generation != self.watch_generation:
                        continue
                    self.watching = False
                    if detected and not self.busy and self.root.state() == "withdrawn":
                        self.root.deiconify()
                        self.root.lift()
                        self.status.set("Pen contact detected. The first touch was only a wake-up signal. Press Start signing to capture NEW disposable strokes.")
                    elif self.root.state() == "withdrawn":
                        self.root.after(1000, self.start_watch)
                    continue
                _, generation, ok, data = event
                if generation != self.generation:
                    continue
                self.busy = False
                self.capture_button.configure(state="disabled")
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
        if self.auto_watch:
            self.root.withdraw()
            self.root.after(500, self.start_watch)
        else:
            self.root.destroy()


def main() -> int:
    p = argparse.ArgumentParser(description="STU-540 staging review dialog")
    p.add_argument("--sdk-adapter", required=True)
    p.add_argument("--auto-watch", action="store_true", help="Wake dialog on first pen contact; needs interactive terminal")
    p.add_argument("--lookup-url", help="Approved staging HTTPS exact National ID endpoint")
    p.add_argument("--company-id", help="Authenticated company UUID")
    p.add_argument("--token-provider", help="Private executable supplying a short-lived operator token")
    p.add_argument("--lookup-config", help="Owner-only JSON config with staging URL, company UUID and private token provider")
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
    lookup_config = None
    if args.lookup_config:
        if any((args.lookup_url, args.company_id, args.token_provider)):
            p.error("Use either --lookup-config or individual lookup arguments")
        lookup_config = load_lookup_config(Path(args.lookup_config))
    elif any((args.lookup_url, args.company_id, args.token_provider)):
        if not all((args.lookup_url, args.company_id, args.token_provider)):
            p.error("Lookup requires --lookup-url, --company-id and --token-provider")
        from client_lookup import validate_lookup_endpoint
        from uuid import UUID
        validate_lookup_endpoint(args.lookup_url)
        UUID(args.company_id)
        lookup_config = {"url": args.lookup_url, "company_id": args.company_id,
                         "token_provider": Path(args.token_provider)}
    ReviewDialog(root, adapter, auto_watch=args.auto_watch, lookup_config=lookup_config)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
