# LoanHub Business Softphone — Vodacom Lesotho Request

## Purpose

LoanHub is implementing a company business-phone application for Android/iOS. Employees sign in with their existing LoanHub company accounts, see only the clients they are authorized to contact, synchronize those clients to the phone contact book, call normal telephone numbers, receive business calls, record calls according to company policy, and transfer a live call to another LoanHub employee.

The client being called does **not** need LoanHub installed. The public telephone leg must be provided through Vodacom/PSTN/SIP rather than by trying to capture ordinary SIM-call audio on the handset.

## What to ask Vodacom for

Ask to speak to **Vodacom Business / Fixed Solutions** and request a technical discussion for a **Vodacom One Connect / SIP / hosted PBX integration with a custom LoanHub softphone**.

Use this description:

> We have a custom business application called LoanHub. We want our authorized employees to make and receive normal Lesotho telephone calls inside our application. Customers should receive calls on ordinary mobile or fixed numbers and should not need our app. We need SIP/PSTN connectivity, inbound business-number routing, employee extensions, call transfer and recording, plus call-event/recording integration with our own backend.

## Required commercial service

Request a quotation and availability for:

1. A Vodacom business telephone number / DID that customers can call.
2. Inbound and outbound PSTN calling through SIP.
3. Enough simultaneous voice channels for the expected number of concurrent LoanHub employee calls.
4. Vodacom One Connect or another hosted PBX option if it can interoperate with the LoanHub application.
5. A test/sandbox arrangement before production activation, if available.
6. Local and international calling rates, monthly rental, channel charges, number charges, recording charges and any setup fees.
7. Capacity upgrade rules so more concurrent channels can be added without changing the LoanHub application.

## Required SIP/PBX capabilities

Confirm that the selected service supports all of the following:

- Outbound calls from LoanHub to normal Vodacom, Econet/other mobile and fixed telephone numbers.
- Inbound calls from the public telephone network to a LoanHub/Vodacom business number.
- A separate extension or routable SIP identity for each LoanHub employee.
- Blind call transfer.
- Attended/consultative transfer, if available.
- SIP REFER or the provider-specific equivalent for transferring an active call.
- Hold and resume.
- Conference calling / adding another employee.
- Call queues and ring groups.
- Busy, no-answer and offline routing.
- Voicemail, if required.
- DTMF support.
- Caller-ID/CLI presentation using the company business number rather than an employee's personal number.
- Call recording for inbound and outbound calls.
- Recording continuity when a call is transferred between employees.

## Required technical handover from Vodacom

Ask the Vodacom technical team to provide the following in writing for the selected service:

### SIP trunk / connection

- SIP registrar, proxy or trunk endpoint/hostname.
- Whether authentication is username/password, IP-based, certificate-based or another method.
- SIP username/trunk identifier.
- SIP password/secret through a secure handover method if password authentication is used.
- Required source/destination IP allowlists.
- SIP signalling port(s).
- Whether SIP over TLS is supported or required.
- RTP/SRTP media port ranges.
- Supported codecs, preferably including PCMA/PCMU and any supported wideband codec.
- NAT requirements.
- Session timer requirements.
- Maximum simultaneous calls/channels.
- Rate limits and CPS (calls per second) limits.

### Public numbers and caller ID

- Assigned business DID(s).
- Exact E.164 format required when dialling Lesotho numbers.
- Approved outbound caller-ID number(s).
- Whether the same DID can be presented from every employee extension.
- Inbound routing destination for each DID.

### Employee extensions

For every employee extension, confirm:

- Extension number.
- SIP URI or routable address format, for example `sip:201@provider-domain` if supported.
- Whether extensions can register from a third-party/custom softphone.
- Whether Vodacom requires use of the One Connect mobile client instead of allowing third-party SIP registration.
- Presence/availability information and whether it can be queried by API.

LoanHub can store the provider-neutral values in each employee's telephony configuration:

```text
telephony_extension = 201
telephony_address   = sip:201@<vodacom-domain>
```

If Vodacom does not provide a SIP URI for an employee, LoanHub can fall back to transferring to that employee's ordinary telephone number, but an internal SIP extension is preferred because it preserves PBX features more reliably.

## Inbound calling requirements

Ask Vodacom exactly how an incoming call should be delivered to LoanHub.

Required flow:

```text
Customer normal phone
        ↓
Vodacom PSTN
        ↓
LoanHub company DID
        ↓
Vodacom SIP / PBX
        ↓
LoanHub telephony/media service
        ↓
Assigned employee / ring group
        ↓
LoanHub mobile application
```

Ask for:

- Inbound SIP trunk details.
- DID-to-SIP routing configuration.
- Ring-group/queue support.
- A way to route an incoming call to a specific employee extension.
- Failover routing if LoanHub is unreachable.
- Any push-notification/mobile-SDK support they provide for incoming softphone calls.

## Call transfer requirement

Explain this exact use case to Vodacom:

> A customer calls LoanHub and Lintle answers. Lintle determines that Filoane should handle the customer. Lintle must be able to tap Transfer in the LoanHub app and hand the live call to Filoane. The customer must remain connected and, where recording is enabled, the recording/audit trail should continue across the transfer.

Ask Vodacom to confirm:

- Blind transfer support.
- Attended transfer support.
- SIP REFER support or the equivalent API/PBX command.
- Whether the transferred call stays inside the same PBX call/session for recording/CDR purposes.
- Whether the original employee, destination employee and transfer timestamp are exposed in CDR/event data.

## Recording requirements

LoanHub should use server/PBX-side recording for reliable two-way audio rather than handset microphone recording.

Ask Vodacom for:

- Automatic recording for inbound and outbound business calls.
- Whether recording can be enabled per company, queue, extension or call.
- Whether recording continues after transfer or conference.
- Recording file format.
- Recording retention options.
- Encryption at rest and in transit.
- How recordings are retrieved.
- Recording download API, secure URL API, SFTP or another supported integration method.
- Recording-ready webhook/event, if available.
- Recording ID correlation with the call/CDR ID.
- Whether a recording notification/announcement can be played automatically.

Do not request or enable covert recording. Company policy and applicable notice/consent requirements must be configured before production recording is enabled.

## APIs, CDR and webhooks

LoanHub needs the telephony platform to report call state back to the backend. Ask whether Vodacom exposes APIs or webhooks for:

- Incoming call started/ringing.
- Outbound call started/ringing.
- Answered.
- Failed/busy/no-answer.
- Hangup/end.
- Transfer initiated/completed/failed.
- Conference participant joined/left.
- Recording started/completed/available.
- Extension registration/presence.
- Call Detail Records (CDR).

For CDR, request at least:

- Unique provider call ID.
- Calling number.
- Called number.
- Direction.
- Start time.
- Answer time.
- End time.
- Billable duration.
- Disposition/status.
- Source and destination extensions.
- Transfer history.
- Recording ID/location.

Ask for API documentation, authentication method, IP restrictions, test credentials and production credentials.

## Security requirements

Ask Vodacom to confirm support for:

- SIP TLS where available.
- SRTP where available.
- IP allowlisting.
- Credential rotation.
- Separate test and production credentials.
- Provider audit logs.
- DDoS/fraud controls.
- International/premium destination restrictions.
- Spend limits and fraud alerts.
- Failover contacts and support escalation procedure.

No SIP secret should ever be embedded in the LoanHub mobile APK. Provider secrets stay on the LoanHub backend/media infrastructure; the mobile app receives only short-lived call/media credentials.

## LoanHub-side integration already prepared

LoanHub already has the following application-side foundation:

- Existing company employee authentication and tenant/role controls.
- Authorized client list from the LoanHub database.
- Native phone-contact synchronization for LoanHub clients.
- Controlled LiveKit/WebRTC employee audio.
- Outbound SIP participant creation.
- Company SIP trunk ID and approved caller-number settings.
- Per-call LoanHub metadata and audit trail.
- Team directory for call transfer.
- SIP call transfer to another configured employee telephony address/phone.
- Recording metadata, retention policy, legal holds and QA structures.

The Vodacom technical handover is therefore needed primarily to activate the PSTN/SIP network leg, inbound routing, production extensions, recording source and provider events.

## Information to take to the meeting

Take the following with you where available:

- Company legal name.
- Company registration documents.
- Company physical/postal address.
- Authorized representative details and identification.
- Billing/contact details.
- Estimated number of employees/extensions.
- Estimated simultaneous calls required initially.
- Expected monthly inbound/outbound call volume.
- Whether international calling is required.
- Desired company caller-ID/business number.
- This document and a simple LoanHub architecture diagram.

Ask Vodacom to confirm their exact corporate onboarding/KYC document requirements before signing; do not assume the list above replaces Vodacom's current application requirements.

## Initial capacity example for quotation

Vodacom should quote at least two options so LoanHub can scale:

```text
Option A — Pilot
5 employee extensions
3–5 simultaneous voice channels
1 business DID
Inbound + outbound calls
Call transfer
Call recording
CDR/API access

Option B — Production
20 employee extensions
10–20 simultaneous voice channels
1 or more business DIDs
Queues/ring groups
Inbound + outbound calls
Call transfer/conference
Call recording
CDR/API/webhooks
Failover and support SLA
```

The actual channel count should be chosen from expected peak concurrency, not simply employee count.

## Questions that must be answered before leaving Vodacom

1. Can our own LoanHub Android/iOS softphone connect to your SIP/One Connect service?
2. If yes, what SIP credentials/endpoint are supplied and how are extensions addressed?
3. Can a normal customer call one Vodacom business number and be routed to our LoanHub employees?
4. Can LoanHub display our company number as outbound caller ID?
5. Do you support blind and attended transfers between employee extensions?
6. Do recordings continue through call transfers?
7. Can recordings be downloaded or fetched through an API?
8. Can we receive real-time call-state webhooks or API events?
9. Can we retrieve full CDR data programmatically?
10. What are the test credentials/environment and production activation steps?
11. What are the monthly, per-channel, per-extension, per-minute and recording costs?
12. What technical support/SLA and escalation contact do we receive?

## Vodacom contact route

Use Vodacom Lesotho Business / Fixed Solutions. Their public business pages advertise Vodacom One Connect, SIP, call transfer and call recording. Their public business contact route lists **155** for new services and **Fixedsales@vodacom.co.ls** for enquiries, with the Vodacom head office at Vodacom Park, 585 Mabile Road, Maseru.

Before the visit, call or email and ask for a **Fixed Solutions / One Connect / SIP technical sales engineer** to be available, because ordinary retail support may not be able to answer API, SIP trunk and integration questions.
