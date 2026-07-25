import smtplib
import ssl
from collections.abc import Callable
from email.message import EmailMessage
from types import TracebackType
from typing import Protocol

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


class SMTPClient(Protocol):
    def __enter__(self) -> "SMTPClient": ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def ehlo(self) -> tuple[int, bytes]: ...

    def starttls(self, *, context: ssl.SSLContext) -> tuple[int, bytes]: ...

    def login(self, user: str, password: str) -> tuple[int, bytes]: ...

    def send_message(self, message: EmailMessage) -> dict[str, tuple[int, bytes]]: ...


SMTPFactory = Callable[[str, int, float], SMTPClient]


class SMTPRejectedError(RuntimeError):
    pass


def _default_factory(host: str, port: int, timeout: float) -> SMTPClient:
    return smtplib.SMTP(host, port, timeout=timeout)


class GmailSMTPDelivery:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        app_password: str,
        timeout: float = 20,
        factory: SMTPFactory = _default_factory,
        use_starttls: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.app_password = app_password
        self.timeout = timeout
        self.factory = factory
        self.use_starttls = use_starttls
        self.accepted = False

    @retry(
        retry=retry_if_exception_type(
            (TimeoutError, OSError, smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected)
        ),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.25, min=0.25, max=1),
        reraise=True,
    )
    def send(self, message: EmailMessage) -> None:
        if self.accepted:
            return
        with self.factory(self.host, self.port, self.timeout) as smtp:
            smtp.ehlo()
            if self.use_starttls:
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
            smtp.login(self.username, self.app_password)
            refused = smtp.send_message(message)
            if refused:
                raise SMTPRejectedError(f"SMTP refused recipients: {sorted(refused)}")
            self.accepted = True
