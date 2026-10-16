# Orbit Email: security guidance

This package supplies message contracts and bounded constructors; it is not a mail security
gateway. The checks below reduce common input and accidental logging risks, but do not validate
mailbox ownership, sender authorization, attachment safety, user consent, or delivery policy.

## Sensitive data and diagnostics

Email addresses, subjects, bodies, attachments, and provider message identifiers can contain
personal or confidential information. The value reprs omit those fields, but explicit property
access returns the original values and applications can still log them. Do not place message
content or recipient addresses in metrics labels, tracing attributes, exception text, audit logs,
or support bundles unless an approved data policy explicitly allows it.

`EmailSendError`, `EmailTemporaryError`, and `EmailPermanentError` do not sanitize exception text.
Provider adapters must create safe, bounded messages instead of forwarding raw SDK errors or
responses, which may include request bodies, credentials, addresses, or service metadata. Chained
exceptions can also appear in logs; decide whether to suppress a cause based on the selected SDK's
diagnostic contents and the application's reporting configuration.

## Untrusted content

- Validate and authorize recipients before constructing or sending a message. Syntax validation
  does not establish that a mailbox exists or that the sender is allowed to contact it.
- HTML body content is preserved as supplied. Escape or sanitize untrusted content with an
  application-appropriate HTML policy before sending; this library has no HTML sanitizer.
- Attachment filenames reject path separators and control characters, but this does not make
  uploaded files safe. Enforce content-type policy, inspect file signatures as needed, scan for
  malware, and store files according to your application's retention rules.
- Media types are checked for token syntax only. A declared type is not verified against bytes.
- Keep BCC values out of visible message headers. The capability exposes envelope recipients, but
  provider adapters are responsible for correct request mapping and BCC privacy.

## Transport and sender identity

The capability has no network transport. Use a provider adapter that verifies TLS certificates,
protect credentials with a secret manager, use least-privilege send permissions, and follow the
provider's sender-domain verification and anti-abuse controls. Avoid disabling TLS verification to
work around certificate errors. Configure rate limits and abuse controls at the application and
provider layers.

Sending an email has external side effects. Protect send operations with the application's
authorization and audit policy. Do not expose an unauthenticated endpoint that accepts arbitrary
recipients or caller-supplied sender addresses.

## Limits and reporting

The constructors bound recipient count, attachment count, and message byte sizes. They are not a
global application memory budget, request-body limit, rate limit, or denial-of-service control.
Apply request limits before buffering uploads, cap concurrent sends, and use a queue when the
application needs durable backpressure. Follow the repository [security policy](../../SECURITY.md)
for vulnerability reporting; do not publish exploitable details in public issues.
