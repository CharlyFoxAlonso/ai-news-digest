import hashlib
import html
from datetime import date
from email.message import EmailMessage
from urllib.parse import urlsplit

from ai_news.models import DigestEntry


def deterministic_message_id(digest_date: date, repository: str, recipient: str) -> str:
    seed = f"{digest_date.isoformat()}|{repository}|{recipient.casefold()}".encode()
    digest = hashlib.sha256(seed).hexdigest()[:32]
    domain = repository.split("/", 1)[-1].replace("_", "-").lower()
    return f"<{digest}@{domain}.github-actions>"


def build_digest_email(
    entries: list[DigestEntry],
    *,
    digest_date: date,
    sender: str,
    recipient: str,
    repository: str,
) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = f"📰 AI News Digest — {digest_date.strftime('%d/%m/%Y')}"
    message["From"] = sender
    message["To"] = recipient
    message["Message-ID"] = deterministic_message_id(digest_date, repository, recipient)
    message.set_content(_plain_body(entries))
    message.add_alternative(_html_body(entries), subtype="html")
    return message


def _plain_body(entries: list[DigestEntry]) -> str:
    if not entries:
        content = "No hubo novedades relevantes entre las fuentes consultadas."
    else:
        blocks = []
        for index, entry in enumerate(entries, 1):
            blocks.append(
                "\n".join(
                    (
                        f"{index}. {entry.article.title}",
                        entry.summary_es,
                        f"Por qué importa: {entry.why_it_matters}",
                        f"Fuente: {entry.article.source_name}",
                        f"Enlace: {_safe_url(str(entry.article.url_canonical))}",
                    )
                )
            )
        content = "\n\n".join(blocks)
    return f"{content}\n\nGenerado automáticamente.\n"


def _html_body(entries: list[DigestEntry]) -> str:
    if not entries:
        content = "<p>No hubo novedades relevantes entre las fuentes consultadas.</p>"
    else:
        cards = []
        for index, entry in enumerate(entries, 1):
            title = html.escape(entry.article.title)
            summary = html.escape(entry.summary_es)
            importance = html.escape(entry.why_it_matters)
            source = html.escape(entry.article.source_name)
            url = html.escape(_safe_url(str(entry.article.url_canonical)), quote=True)
            cards.append(
                f'<article style="margin:0 0 24px"><h2>{index}. {title}</h2>'
                f"<p>{summary}</p><p><strong>Por qué importa:</strong> {importance}</p>"
                f'<p>Fuente: {source} · <a href="{url}">Leer noticia</a></p></article>'
            )
        content = "".join(cards)
    return (
        '<!doctype html><html lang="es"><body style="font-family:Arial,sans-serif;'
        'max-width:680px;margin:auto;color:#18212f"><h1>AI News Digest</h1>'
        f"{content}<hr><p>Generado automáticamente.</p></body></html>"
    )


def _safe_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("digest contains an unsafe URL")
    return value
