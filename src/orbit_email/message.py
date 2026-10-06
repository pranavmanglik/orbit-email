# Copyright 2026-present Orbit Contributors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Bounded email messages and provider-neutral asynchronous sender contracts."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from email.errors import HeaderParseError
from email.headerregistry import Address
from typing import Protocol, TypeVar, runtime_checkable

_MAX_ADDRESS_LENGTH = 320
_MAX_DISPLAY_NAME_LENGTH = 256
_MAX_RECIPIENTS = 100
_MAX_SUBJECT_BYTES = 998
_MAX_BODY_BYTES = 10 * 1024 * 1024
_MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
_MAX_TOTAL_BYTES = 20 * 1024 * 1024
_MAX_ATTACHMENTS = 10
_MAX_FILENAME_BYTES = 255
_MEDIA_TYPE = re.compile(r"[A-Za-z0-9!#$&^_.+-]{1,64}/[A-Za-z0-9!#$&^_.+-]{1,64}\Z")
_T = TypeVar("_T")


@dataclass(frozen=True, slots=True, repr=False)
class EmailAddress:
    """Validated single mailbox with explicit redaction for address and display name."""

    _header_address: Address = field(repr=False)

    def __init__(self, addr_spec: str, *, display_name: str = "") -> None:
        """Parse one mailbox using Python's RFC-aware header address representation."""
        if not isinstance(addr_spec, str) or not isinstance(display_name, str):
            raise TypeError("email address and display name must be strings.")
        if not addr_spec or len(addr_spec) > _MAX_ADDRESS_LENGTH:
            raise ValueError("email address must be non-empty and at most 320 characters.")
        if len(display_name) > _MAX_DISPLAY_NAME_LENGTH or _has_control(display_name):
            raise ValueError("display name is invalid or too long.")
        try:
            parsed = Address(display_name=display_name, addr_spec=addr_spec)
        except (ValueError, TypeError, HeaderParseError):
            raise ValueError("email address is invalid.") from None
        if not parsed.username or not parsed.domain:
            raise ValueError("email address must include a mailbox and domain.")
        object.__setattr__(self, "_header_address", parsed)

    @property
    def addr_spec(self) -> str:
        """Return the mailbox address for explicit use by an adapter."""
        return self._header_address.addr_spec

    @property
    def display_name(self) -> str:
        """Return the optional display name for an explicit message-rendering decision."""
        return self._header_address.display_name

    @property
    def header_address(self) -> Address:
        """Return the immutable standard-library address structure for header encoding."""
        return self._header_address

    def __repr__(self) -> str:
        """Avoid exposing personally identifying mailbox data in logs or diagnostics."""
        return "EmailAddress(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class EmailAttachment:
    """Bounded in-memory attachment with a safe filename and syntactically checked media type."""

    filename: str = field(repr=False)
    media_type: str
    content: bytes = field(repr=False)

    def __post_init__(self) -> None:
        """Reject path-like names, header controls, invalid media types, and oversized content."""
        if (
            not isinstance(self.filename, str)
            or not self.filename
            or len(self.filename) > _MAX_FILENAME_BYTES
            or len(self.filename.encode("utf-8")) > _MAX_FILENAME_BYTES
            or self.filename in {".", ".."}
            or "/" in self.filename
            or "\\" in self.filename
            or _has_control(self.filename)
        ):
            raise ValueError("attachment filename must be a safe basename of at most 255 bytes.")
        if not isinstance(self.media_type, str) or not _MEDIA_TYPE.fullmatch(self.media_type):
            raise ValueError("attachment media_type must be a type/subtype token pair.")
        if not isinstance(self.content, bytes):
            raise TypeError("attachment content must be bytes.")
        if len(self.content) > _MAX_ATTACHMENT_BYTES:
            raise ValueError("attachment content exceeds the 10 MiB limit.")

    def __repr__(self) -> str:
        """Expose only bounded metadata, never attachment name or content."""
        return f"EmailAttachment(media_type={self.media_type!r}, size={len(self.content)})"


@dataclass(frozen=True, slots=True, repr=False)
class EmailMessage:
    """Immutable bounded message; recipient and content values are excluded from its repr."""

    from_address: EmailAddress = field(repr=False)
    to: tuple[EmailAddress, ...] = field(repr=False)
    subject: str = field(repr=False)
    text_body: str | None = field(default=None, repr=False)
    html_body: str | None = field(default=None, repr=False)
    cc: tuple[EmailAddress, ...] = field(default=(), repr=False)
    bcc: tuple[EmailAddress, ...] = field(default=(), repr=False)
    attachments: tuple[EmailAttachment, ...] = field(default=(), repr=False)

    def __post_init__(self) -> None:
        """Normalize tuples and enforce message size, recipient, and header safety limits."""
        if not isinstance(self.from_address, EmailAddress):
            raise TypeError("from_address must be an EmailAddress.")
        recipient_total = 0
        for name in ("to", "cc", "bcc"):
            recipients = getattr(self, name)
            if isinstance(recipients, (str, bytes)):
                raise TypeError(f"{name} must be a sequence of EmailAddress values.")
            normalized = _bounded_tuple(recipients, _MAX_RECIPIENTS, name)
            if any(not isinstance(address, EmailAddress) for address in normalized):
                raise TypeError(f"{name} must contain only EmailAddress values.")
            recipient_total += len(normalized)
            object.__setattr__(self, name, normalized)
        if not recipient_total:
            raise ValueError("email message must have at least one recipient.")
        if recipient_total > _MAX_RECIPIENTS:
            raise ValueError("email message cannot have more than 100 recipients.")

        if not isinstance(self.subject, str) or not self.subject.strip():
            raise ValueError("subject must be a non-empty string.")
        if (
            len(self.subject) > _MAX_SUBJECT_BYTES
            or len(self.subject.encode("utf-8")) > _MAX_SUBJECT_BYTES
            or _has_control(self.subject)
        ):
            raise ValueError("subject is invalid or exceeds 998 UTF-8 bytes.")
        if self.text_body is None and self.html_body is None:
            raise ValueError("email message must have a text body, HTML body, or both.")
        total_body_bytes = 0
        for name in ("text_body", "html_body"):
            body = getattr(self, name)
            if body is not None:
                if not isinstance(body, str):
                    raise TypeError(f"{name} must be a string or None.")
                if len(body) > _MAX_BODY_BYTES or "\x00" in body:
                    raise ValueError(f"{name} is invalid or exceeds the 10 MiB limit.")
                total_body_bytes += len(body.encode("utf-8"))
        if total_body_bytes > _MAX_BODY_BYTES:
            raise ValueError("combined message bodies exceed the 10 MiB limit.")

        if isinstance(self.attachments, (str, bytes)):
            raise TypeError("attachments must be a sequence of EmailAttachment values.")
        attachments = _bounded_tuple(self.attachments, _MAX_ATTACHMENTS, "attachments")
        if any(not isinstance(attachment, EmailAttachment) for attachment in attachments):
            raise TypeError("attachments must contain only EmailAttachment values.")
        if len(attachments) > _MAX_ATTACHMENTS:
            raise ValueError("email message cannot have more than 10 attachments.")
        object.__setattr__(self, "attachments", attachments)
        total_size = total_body_bytes + sum(len(item.content) for item in attachments)
        if total_size > _MAX_TOTAL_BYTES:
            raise ValueError("message bodies and attachments exceed the 20 MiB total limit.")

    @property
    def envelope_recipients(self) -> tuple[EmailAddress, ...]:
        """Return all envelope recipients, including BCC values hidden from repr."""
        return self.to + self.cc + self.bcc

    def __repr__(self) -> str:
        """Provide useful bounded diagnostics without PII, message content, or attachment names."""
        return (
            "EmailMessage("
            f"recipient_count={len(self.envelope_recipients)}, "
            f"attachment_count={len(self.attachments)})"
        )


@dataclass(frozen=True, slots=True, repr=False)
class EmailSendReceipt:
    """Provider-neutral acceptance receipt with the provider message ID kept private in repr."""

    message_id: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Validate optional bounded opaque provider identifier."""
        if self.message_id is not None and (
            not isinstance(self.message_id, str)
            or not self.message_id
            or len(self.message_id) > 512
            or _has_control(self.message_id)
        ):
            raise ValueError("message_id must be a bounded string without control characters.")

    def __repr__(self) -> str:
        """Avoid leaking provider identifiers that may contain correlation metadata."""
        return "EmailSendReceipt(<redacted>)"


class EmailSendError(Exception):
    """Safe provider-neutral failure without addresses, message bodies, or SDK diagnostics."""


class EmailTemporaryError(EmailSendError):
    """A potentially transient delivery failure; retry safety depends on provider acceptance."""


class EmailPermanentError(EmailSendError):
    """A non-retryable delivery failure such as a rejected address or policy violation."""


@runtime_checkable
class EmailSender(Protocol):
    """Async email transport capability; implementations own and close provider resources."""

    async def send(self, message: EmailMessage) -> EmailSendReceipt:
        """Submit one message without implicit retries; cancellation must propagate unchanged."""

    async def aclose(self) -> None:
        """Close owned transport resources after in-flight sends finish or are cancelled."""


def _has_control(value: str) -> bool:
    """Return whether a header-facing value contains Unicode control characters."""
    return any(unicodedata.category(character) == "Cc" for character in value)


def _bounded_tuple(values: Iterable[_T], limit: int, name: str) -> tuple[_T, ...]:
    """Materialize at most limit+1 items so infinite or oversized iterables fail promptly."""
    try:
        iterator = iter(values)
    except TypeError:
        raise TypeError(f"{name} must be a sequence.") from None
    result: list[_T] = []
    for _ in range(limit + 1):
        try:
            result.append(next(iterator))
        except StopIteration:
            return tuple(result)
    raise ValueError(f"{name} exceeds the {limit}-item limit.")
