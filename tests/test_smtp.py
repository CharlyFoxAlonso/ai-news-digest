import smtplib
import socket
from email.message import EmailMessage

import pytest
from aiosmtpd.controller import Controller

from ai_news.delivery.smtp import GmailSMTPDelivery, SMTPRejectedError


class FakeSMTP:
    def __init__(self, outcomes, calls) -> None:
        self.outcomes = outcomes
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def ehlo(self):
        return 250, b"ok"

    def starttls(self, *, context):
        self.calls.append("starttls")
        return 220, b"ready"

    def login(self, user, password):
        self.calls.append(("login", user, password))
        return 235, b"ok"

    def send_message(self, message):
        self.calls.append("send")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def message() -> EmailMessage:
    value = EmailMessage()
    value["From"] = "sender@example.com"
    value["To"] = "reader@example.com"
    value.set_content("Digest")
    return value


def test_smtp_accepted_and_not_retried_after_acceptance() -> None:
    calls = []
    outcomes = [{}]
    delivery = GmailSMTPDelivery(
        host="smtp.example.com",
        port=587,
        username="user",
        app_password="secret",
        factory=lambda *_: FakeSMTP(outcomes, calls),
    )
    delivery.send(message())
    delivery.send(message())
    assert calls.count("send") == 1
    assert "starttls" in calls


def test_transient_failure_is_retried_before_acceptance() -> None:
    calls = []
    outcomes = [smtplib.SMTPServerDisconnected("temporary"), {}]
    delivery = GmailSMTPDelivery(
        host="smtp.example.com",
        port=587,
        username="user",
        app_password="secret",
        factory=lambda *_: FakeSMTP(outcomes, calls),
    )
    delivery.send(message())
    assert calls.count("send") == 2


def test_rejected_recipient_is_not_retried() -> None:
    calls = []
    outcomes = [{"reader@example.com": (550, b"rejected")}]
    delivery = GmailSMTPDelivery(
        host="smtp.example.com",
        port=587,
        username="user",
        app_password="secret",
        factory=lambda *_: FakeSMTP(outcomes, calls),
    )
    with pytest.raises(SMTPRejectedError):
        delivery.send(message())
    assert calls.count("send") == 1


def test_acceptance_against_local_smtp_server() -> None:
    messages = []

    class Handler:
        async def handle_DATA(self, _server, _session, envelope):
            messages.append(envelope.content)
            return "250 accepted"

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    controller = Controller(Handler(), hostname="127.0.0.1", port=port)
    controller.start()
    try:
        delivery = GmailSMTPDelivery(
            host="127.0.0.1",
            port=port,
            username="",
            app_password="",
            use_starttls=False,
            authenticate=False,
        )
        delivery.send(message())
    finally:
        controller.stop()
    assert delivery.accepted
    assert len(messages) == 1
