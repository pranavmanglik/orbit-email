# Orbit Email: operations

This guide describes operating the provider-neutral email contract. `orbit-email` contains no
transport or provider client, so connection, timeout, retry, and provider quota settings belong to
the selected adapter and must be checked in that adapter's documentation.

## Configuration and credentials

The capability package defines no environment variables or configuration object. Configure the
chosen adapter through the application's configuration system. Supply credentials through a
secret manager or deployment secret mechanism; avoid command-line arguments, committed `.env`
files, and logs. Use least-privilege credentials scoped to the sending identity and rotate them
according to the provider's process.

No default credentials are provided. Do not assume that installing `orbit-email` configures a
working sender.

## Constructing messages

All message bodies and attachment bytes are held in memory. Build messages only after applying
application authorization and consent checks. The current bounds are 100 total recipients, 10
attachments, 10 MiB for an individual text or HTML body, 10 MiB per attachment, and 20 MiB combined
body and attachment bytes. The transport request may be larger due to MIME and base64 encoding;
check the provider's request-size limit and leave headroom. These limits do not provide streaming
or protect the application from constructing large source objects before calling the constructors.

Send BCC recipients as envelope recipients while omitting them from visible message headers. The
capability exposes `envelope_recipients` but does not serialize MIME or decide which headers an
adapter emits. Adapter authors must preserve BCC privacy when translating a message to provider
requests.

## Timeouts, retries, and duplicate delivery

The sender API makes one logical call and does not retry automatically. Set connection and request
timeouts in the adapter and bound concurrent sends to match provider quotas and application
capacity. A timeout or connection loss can occur after provider acceptance. Therefore:

1. Classify a failure as temporary only when retrying could plausibly succeed.
2. Do not interpret `EmailTemporaryError` as proof that no message was accepted.
3. Use provider idempotency only where the adapter documents the exact key scope and retention.
4. Apply bounded retry count, exponential backoff, and jitter in the application or a separately
   chosen queue/worker system; the capability provides none of these.
5. Record safe correlation identifiers and outcome state without recording bodies, credentials, or
   recipient addresses in general-purpose logs.

`EmailPermanentError` signals that automatic retry is inappropriate without changing the input or
policy. Provider-specific classification belongs to the adapter and can vary by API operation.

## Shutdown and health

During graceful shutdown, stop accepting new application work, drain or cancel active send tasks
within the deployment's shutdown deadline, then call `aclose()` on each owned sender. Implementors
should make repeated close behavior explicit and ensure their SDK clients and network pools are
released. The protocol does not prescribe a health check, readiness policy, or delivery probe; a
successful connectivity check does not prove the sender identity is authorized or deliverable.

## Production validation

Before deployment, validate the chosen adapter against a non-production account: credential
loading and rotation, TLS verification, sender-domain authorization, rate limits, request-size
limits, timeout behavior after possible acceptance, cancellation, shutdown under active sends,
provider error classification, and duplicate handling. Test bounce, complaint, suppression, and
delivery-event processing separately if the application needs those capabilities. Local contract
tests cannot verify provider acceptance or deliverability.
