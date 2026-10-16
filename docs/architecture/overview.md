# Orbit Email: architecture and contract boundaries

## Responsibility

`orbit-email` defines bounded, immutable message values and an asynchronous sender protocol. It
does not connect to a mail server, render templates, enqueue messages, or claim delivery. Provider
adapters implement `EmailSender`; applications decide when to send, what to retry, and how to
observe delivery outcomes.

```text
application ── builds EmailMessage ──> EmailSender
                                      ├── SMTP/provider adapter
                                      └── provider SDK, credentials, transport, lifecycle
```

The dependency direction is intentional: this capability package has no provider SDK dependency.
Adapters may depend on `orbit-email`, but the capability must not import adapters or Core runtime
implementation details.

## Message values

- `EmailAddress` parses a mailbox through Python's standard `email.headerregistry.Address` type.
  It validates syntax and bounded display-name/address input; it cannot establish that a mailbox
  exists, accepts mail, or belongs to the caller.
- `EmailMessage` requires at least one envelope recipient and at least one text or HTML body. It
  normalizes recipient and attachment iterables to immutable tuples and bounds iteration before
  materializing them, including for accidentally unbounded iterators.
- `EmailAttachment` stores bytes in memory. Names are basenames; media types are syntactically
  checked tokens. The package does not inspect file contents, detect malware, or prove that a MIME
  type matches those contents.
- `EmailSendReceipt` contains an optional opaque provider identifier. Its repr hides that value.

Current defaults are 100 recipients across To/Cc/Bcc, 10 attachments, 10 MiB per body, 10 MiB per
attachment, 20 MiB combined body and attachment bytes, and a 998-byte subject. These are API limits,
not a guarantee that a provider accepts a message of that size. MIME/base64 encoding, provider
limits, and transport overhead can make the transmitted request larger.

Message reprs omit addresses, subjects, bodies, attachment filenames, and attachment bytes. This
reduces accidental disclosure in routine diagnostics; it does not protect values explicitly read
by application code, exception messages, tracing attributes, or provider SDK logs.

## Sender lifecycle and errors

`send()` performs one submission attempt. Implementations must not hide retries, must propagate
async task cancellation, and must use `aclose()` to release resources they own. The adapter owns
its SDK clients and connection pools; callers should stop new work, await or cancel in-flight work,
then close the sender once during application shutdown. The protocol does not itself serialize
concurrent calls or make `aclose()` safe to race with `send()`; adapters document and enforce their
concurrency policy.

Adapters map failures to `EmailTemporaryError` or `EmailPermanentError`. The exception classes
accept ordinary Python exception text and do not redact it. Adapter authors must construct
bounded, safe messages and avoid recipient addresses, message content, credentials, and raw
provider response bodies. Preserve the underlying exception as a chained cause only if doing so
cannot expose sensitive SDK diagnostics through the application's logging and reporting path.

An error is not proof that a provider rejected the message. A connection may time out after
acceptance. Retrying can produce duplicates unless the provider supports an idempotency key and
the adapter documents how it is applied. The generic contract has no idempotency key, exactly-once
delivery, queue, ordering, persistence, or delivery-status callback.

## Content and delivery policy

The package does not sanitize HTML, validate sender-domain authorization (SPF/DKIM/DMARC), apply
unsubscribe or consent policy, classify bounces, or rate-limit recipients. Applications and
adapters must apply their relevant policy. Treat HTML, attachment content, recipient lists, and
provider credentials as sensitive inputs. Do not use repr redaction as a substitute for access
control or data-retention policy.

The public API is alpha. Contract changes may occur before a stable release; adapters should
pin compatible versions and test the specific provider behavior they depend on.
