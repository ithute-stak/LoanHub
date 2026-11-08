# Provider-specific integration work that cannot be inferred from code

This bundle does **not** claim to know Vodacom Lesotho M-PESA, Econet, Golink,
or card acquiring production callback message layouts, endpoint credentials,
provider signatures, signed headers, replay fields or settlement rules.

Do not implement a fake "generic HMAC" as if it authenticated a real provider.
To complete a real adapter, obtain an approved spec and test credentials from
that provider, then implement all of the following under independent review:

1. Identify transport and allowlisted endpoint; TLS and mutual TLS if required.
2. Verify the authentic signature/auth mechanism over the provider's **exact**
   signed bytes, timestamp, merchant identity, replay nonce, reference and amount.
3. Treat late and repeated webhooks as separate events with unique provider IDs.
4. Check the independent merchant account/shortcode binding, tenant, payee,
   currency, approved mandate and limits before any financial activity.
5. Persist durable callback evidence and state under a single reviewed DB
   transaction with an immutable audit event, outbox and unique posting key.
6. Treat network timeouts as UNKNOWN pending provider inquiry; never assume
   failure and automatically send a second debit.
7. Obtain bank/provider settlement files and reconcile them separately.
8. Use provider sandbox tests, failure injection, recovery tests and written
   certification before proposing production enablement.

**Preserve existing direct M-PESA integration and shortcode 38542**. Golink
must remain optional and replaceable, not a mandatory upstream provider.
