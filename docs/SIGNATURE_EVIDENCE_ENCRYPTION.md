# Wacom signature evidence encryption (foundation)

The `signature_evidence_vault` service encrypts candidate handwritten-signature
evidence using AES-256-GCM, a fresh random 96-bit nonce, and authenticated
associated data binding exact company, borrower, signing session and contract
hash. Blob version `LHSV1` is used for format separation.

**Deployment requirement:** provision a dedicated random 32-byte key from a
secret manager and pass its Base64 form to the service; do not reuse JWT keys,
database passwords or commit keys. Plan secure backup, rotation and recovery
before production. Example to generate a new key locally (do not paste its
result into chat or commit it):

```sh
python3 -c 'import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())'
```

No API invokes this module yet. Before enabling real capture we must:
- Verify tenant, borrower identity, explicit consent and immutable contract
  digest with a locked, unexpired signing session.
- Accept only authenticated workstation evidence; do not trust the HTTP
  client claiming `input_method=wacom_stu`.
- Validate and normalize pen traces, store ciphertext and digest, and
  reconcile failed DB transactions with object storage cleanup.
- Authorize any saved signature use separately for each contract and log
  all access and use.
- Finalize the PDF and signing status only after immutable evidence is
  persisted and the complete flow passes independent security review.

The object store receives **ciphertext only**. Encryption does not prove
signer identity, legal consent, or finalization. The module is currently
standalone, used by tests only. Existing OTP signing is unaffected.
