# LoanHub → IthutePay signed read-only Batlokoa handshake

Implementation is **disabled by default**. Existing LoanHub LelefaPayGate payments, provider shortcode routing, callbacks and Golink integration are untouched.

## Fixed trusted identities

- LoanHub Batlokoa company: `4236a21f-5164-48aa-90f3-a35eccd23ae2`
- IthutePay registered master merchant: `3cc13734-5cd3-4ab4-9e4b-d378b715fa3f`
- Dedicated inactive IthutePay application: `153b9348-e9f1-4115-9bd5-48fa761b48b8`
- Existing Vodacom M-PESA shortcode: `38542`

## Deployment and security configuration

The client uses **different** configuration keys from the payment gateway:

```ini
ITHUTEPAY_BATLOKOA_HANDSHAKE_ENABLED=false
ITHUTEPAY_BATLOKOA_HANDSHAKE_BASE_URL=https://api.pay.ithute.co.ls
ITHUTEPAY_BATLOKOA_HANDSHAKE_TIMEOUT_SECONDS=5
# ITHUTEPAY_BATLOKOA_HANDSHAKE_SECRET=<provision securely; do not commit>
```

On the IthutePay receiver: `LOANHUB_BATLOKOA_HANDSHAKE_ENABLED=false` and `LOANHUB_BATLOKOA_HANDSHAKE_SECRET` must be configured. Generate **one fresh dedicated random value of at least 32 characters** with your approved secrets manager and provision identical values into both services, without printing it in logs or chat. Do not reuse M-PESA credentials, JWT, or API keys. Ensure IthutePay Redis is reachable for fail-closed nonce replay handling.

Both flags should remain disabled until the reviewed deployments are installed and staging security checks pass. Config values need to be provided through the existing container secret configuration process; just adding a value to a local terminal does not inject it into the container.

## Read-only verification command

When enabled and provisioned, run inside LoanHub backend:

```bash
sudo docker exec -i -w /app loanhub-backend-1 \\
  python -m scripts.verify_batlokoa_ithutepay_handshake
```

The CLI first ensures there is exactly one active LoanHub company with the verified ID; only then sends a signed HTTPS GET. An HMAC timestamp/nonce signature is valid for ±120 seconds, with server-side Redis replay rejection. Redirects are not followed. Response must show the exact inactive application, merchant and shortcode and explicitly disabled financial flags.

The client does **not** generate an API key, issue payment instructions, post fees, or enable custody. The zero-platform-fee policy remains a preview until an approved posting path has accounting tests and operational controls.
