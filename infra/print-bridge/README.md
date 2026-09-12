# LoanHub Local Print Bridge

Register an agent in LoanHub, then configure this application with the returned one-time secret. The bridge stores only an agent ID and revocable agent secret in a local file protected with mode `0600`; it does not store a user's password or JWT.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python loanhub_print_bridge.py printers
python loanhub_print_bridge.py configure --api-url https://example.com/api/v1 --agent-id ... --agent-secret ... --printer PRINTER_NAME
python loanhub_print_bridge.py run
```

Production packaging should run it as a signed desktop/service installer and use OS keyring storage.
