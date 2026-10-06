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
from __future__ import annotations

from itertools import repeat

import pytest

from orbit_email import EmailAddress, EmailAttachment, EmailMessage, EmailSendReceipt


def address(value: str = "person@example.test", *, display_name: str = "") -> EmailAddress:
    return EmailAddress(value, display_name=display_name)


def message(**overrides: object) -> EmailMessage:
    values: dict[str, object] = {
        "from_address": address("sender@example.test"),
        "to": (address(),),
        "subject": "A safe message",
        "text_body": "Hello",
    }
    values.update(overrides)
    return EmailMessage(**values)  # type: ignore[arg-type]


def test_address_uses_standard_header_representation_and_redacts_repr() -> None:
    value = address("person@example.test", display_name="Private Name")

    assert value.header_address.addr_spec == "person@example.test"
    assert value.header_address.display_name == "Private Name"
    assert "person@example.test" not in repr(value)
    assert "Private Name" not in repr(value)


@pytest.mark.parametrize(
    "addr_spec,display_name",
    [
        ("", ""),
        ("<>@example.test", ""),
        ("person@example.test\r\nBcc:attacker@example.test", ""),
        ("person@example.test", "Name\nBcc:attacker@example.test"),
    ],
)
def test_address_rejects_invalid_and_header_injection_values(
    addr_spec: str, display_name: str
) -> None:
    with pytest.raises(ValueError):
        EmailAddress(addr_spec, display_name=display_name)


def test_message_hides_personal_data_and_keeps_bcc_in_envelope() -> None:
    bcc = address("hidden@example.test")
    mail = message(
        to=(address("visible@example.test"),),
        bcc=(bcc,),
        subject="Private subject",
        text_body="Private body",
    )

    assert mail.envelope_recipients == mail.to + mail.bcc
    representation = repr(mail)
    for private_value in (
        "visible@example.test",
        "hidden@example.test",
        "Private subject",
        "Private body",
    ):
        assert private_value not in representation


def test_message_rejects_empty_recipients_and_empty_bodies() -> None:
    with pytest.raises(ValueError, match="at least one recipient"):
        message(to=())
    with pytest.raises(ValueError, match="text body"):
        message(text_body=None)


def test_message_rejects_header_injection_and_recipient_overflow() -> None:
    with pytest.raises(ValueError, match="subject"):
        message(subject="hello\r\nBcc:attacker@example.test")
    with pytest.raises(ValueError, match="100-item limit"):
        message(to=tuple(address(f"user{index}@example.test") for index in range(101)))


def test_recipient_iterables_are_bounded_before_materializing() -> None:
    with pytest.raises(ValueError, match="to exceeds"):
        message(to=repeat(address()))


def test_message_limits_utf8_body_size() -> None:
    with pytest.raises(ValueError, match="10 MiB"):
        message(text_body="x" * (10 * 1024 * 1024 + 1))


@pytest.mark.parametrize("filename", ["../secret.txt", "folder\\secret.txt", "bad\r\nname.txt"])
def test_attachment_rejects_path_and_header_injection(filename: str) -> None:
    with pytest.raises(ValueError, match="filename"):
        EmailAttachment(filename, "text/plain", b"contents")


def test_attachment_redacts_name_and_content_in_repr() -> None:
    attachment = EmailAttachment("private.txt", "text/plain", b"private contents")

    assert "private.txt" not in repr(attachment)
    assert "private contents" not in repr(attachment)


def test_message_enforces_attachment_and_combined_size_limits() -> None:
    attachments = tuple(
        EmailAttachment(f"file-{index}.bin", "application/octet-stream", b"x")
        for index in range(11)
    )
    with pytest.raises(ValueError, match="10-item limit"):
        message(attachments=attachments)

    content = b"y" * (10 * 1024 * 1024)
    attachments = (
        EmailAttachment("first.bin", "application/octet-stream", content),
        EmailAttachment("second.bin", "application/octet-stream", content),
    )
    with pytest.raises(ValueError, match="20 MiB"):
        message(text_body="x", attachments=attachments)


def test_receipt_repr_redacts_provider_identifier() -> None:
    receipt = EmailSendReceipt("provider-private-id")

    assert "provider-private-id" not in repr(receipt)
