#!/usr/bin/env python3
"""Read-only, fail-closed preflight for the *standalone* Data Center test stack."""
import os
import pathlib
import sys
from urllib.parse import urlsplit

root = pathlib.Path(__file__).resolve().parents[1]
errors = []
def fail(reason):
    errors.append(reason)

expected = root / "compose.dc-cert.yml"
if not expected.is_file():
    fail("Dedicated compose file missing")
if (root / ".env.dc-staging").is_symlink():
    fail("Staging env file must not be a symlink")
envfile = root / ".env.dc-staging"
if not envfile.is_file():
    fail("Create a separate .env.dc-staging (never copy production secrets)")
secrets = root / "dc-cert-secrets"
if secrets.is_symlink() or not secrets.is_dir():
    fail("Create dedicated dc-cert-secrets directory; no symlinks")
else:
    for filename in ("jwt_private.pem", "jwt_public.pem"):
        f = secrets / filename
        if not f.is_file() or f.is_symlink():
            fail(f"Missing isolated signing material: {filename}")
        elif f.stat().st_size == 0:
            fail(f"Empty signing material: {filename}")
    prod = root / "secrets"
    if prod.exists() and prod.resolve() == secrets.resolve():
        fail("Test signing material overlaps production secrets")

values = {}
if envfile.is_file():
    for raw in envfile.read_text().splitlines():
        item = raw.strip()
        if not item or item.startswith("#"):
            continue
        if "=" not in item:
            fail("Malformed staging env line")
            continue
        key, value = item.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")

required = ("DC_CERT_DB_PASSWORD", "DC_CERT_APP_ORIGIN", "DC_CERT_API_URL")
for key in required:
    if not values.get(key) and not os.environ.get(key):
        fail(f"Missing {key}")

production_hosts = {"loanhub.co.ls", "www.loanhub.co.ls", "api.loanhub.co.ls", "batlokoa.co.ls", "www.batlokoa.co.ls"}
for key in ("DC_CERT_APP_ORIGIN", "DC_CERT_API_URL"):
    value = os.environ.get(key) or values.get(key, "")
    try:
        url = urlsplit(value)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.fragment or url.query:
            fail(f"{key} must be a clean, dedicated HTTPS URL")
        if url.hostname in production_hosts or url.hostname.endswith(".loanhub.co.ls") and not url.hostname.startswith("staging."):
            fail(f"{key} must not point to a production endpoint")
    except ValueError:
        fail(f"Invalid URL in {key}")

for forbidden in ("LOANHUB_ENV_FILE", "COMPOSE_PROJECT_NAME", "LOANHUB_IMAGE_TAG"):
    if forbidden in values:
        fail(f"{forbidden} must not be set in staging env file")
if values.get("ENVIRONMENT", "").lower() == "production":
    fail("Staging configuration must not declare production")
if values.get("DB_HOST", "") not in ("", "dc-db"):
    fail("Staging DB_HOST must resolve only to isolated dc-db")
if values.get("REDIS_URL", "") not in ("", "redis://dc-redis:6379/0"):
    fail("Staging Redis must be isolated")
if any(key in values for key in ("JWT_PRIVATE_KEY", "JWT_SECRET", "JWT_PUBLIC_KEY")):
    fail("Use isolated key files, not inline JWT secrets")

# Fail closed on inherited production integration credentials and destinations.
# Staging is a directory/browser certification stack, not a payment or messaging pilot.
sensitive_fragments = (
    "MPESA", "M_PESA", "ECOCASH", "GOLINK", "NEDBANK",
    "PAYMENT", "DISBURSE", "BANK_API", "SMS", "SMTP", "TWILIO",
    "SENDGRID", "RESEND", "WEBHOOK", "S3_", "AWS_", "MINIO",
    "PRODUCTION_DATABASE_URL", "DATABASE_URL", "CELERY_BROKER",
)
for key, value in values.items():
    if value and any(fragment in key.upper() for fragment in sensitive_fragments):
        fail(f"Unexpected integration setting {key}: remove it from browser-test staging")
    if key.upper() in ("DB_PASSWORD", "DB_USER", "DB_NAME", "DB_HOST", "REDIS_URL") and value:
        fail(f"Set isolated infrastructure values only through dedicated Compose settings: {key}")
for key in ("DC_CERT_APP_ORIGIN", "DC_CERT_API_URL"):
    value = os.environ.get(key) or values.get(key, "")
    if "localhost" in value.lower() or "127.0.0.1" in value:
        fail(f"{key} must use a dedicated HTTPS staging hostname")

if errors:
    for reason in errors:
        print("BLOCKED:", reason, file=sys.stderr)
    sys.exit(1)
print("PASS: local staging prerequisite checks (no containers started; no external endpoints verified)")
