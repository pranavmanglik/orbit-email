# Orbit Email

`orbit-email` provides a provider-neutral asynchronous message and sender contract. The package
uses only Python's standard library and does not choose an SMTP server or email service:

```bash
python -m pip install orbit-email
```

Build `EmailMessage` values from `EmailAddress` mailboxes, then pass them to an `EmailSender`
adapter:

```python
from orbit_email import EmailAddress, EmailMessage, EmailSender

message = EmailMessage(
    from_address=EmailAddress("receipts@example.com", display_name="Shop"),
    to=(EmailAddress("customer@example.net"),),
    subject="Your receipt",
    text_body="Thank you for your order.",
)


async def deliver(sender: EmailSender) -> None:
    try:
        receipt = await sender.send(message)
        print("accepted")
    finally:
        await sender.aclose()
```

`EmailAddress` uses Python's [`email.headerregistry.Address`](https://docs.python.org/3/library/email.headerregistry.html#email.headerregistry.Address)
representation for Internet Message Format mailbox syntax and does not claim that a mailbox exists
or can receive mail. Message subjects reject Unicode control characters, body
size is bounded to 10 MiB, recipient count to 100, attachment count to 10, each attachment to
10 MiB, and combined bodies plus attachments to 20 MiB. Attachment names cannot contain path
separators or header controls. BCC recipients remain available in the envelope list; message,
address, attachment, and receipt representations redact personal or message data.
HTML bodies are transmitted as supplied and are not sanitized or rendered by this package; callers
must apply their own content policy before sending untrusted HTML. Attachment bytes and media types
are also caller-supplied and should be validated against application policy.

Senders own provider SDKs, credentials, connections, retry policy, and shutdown. They must map
provider failures to `EmailTemporaryError` or `EmailPermanentError` without including message
content or recipient data in exception text, and propagate task cancellation. A temporary error
does not prove the provider failed to accept the message: delivery may have succeeded before a
timeout. The contract makes no exactly-once, idempotency, queueing, or delivery guarantee. Callers
must choose retry behavior based on the adapter's documented provider semantics.

This package includes no SMTP server, cloud email SDK, template rendering, tracking, queue, or
provider adapter. The public API is pre-alpha and not stable.

## Documentation

The package-specific guides cover [architecture](docs/architecture/overview.md), [operations and security](docs/operations/README.md), and [development](docs/development/README.md), with [security guidance](docs/security/overview.md). The [documentation index](docs/README.md) links to the full package overview and project policies.

## Development

```bash
python -m pip install -e '.[dev]'
pytest
ruff check .
mypy
```

Licensed under Apache-2.0.

