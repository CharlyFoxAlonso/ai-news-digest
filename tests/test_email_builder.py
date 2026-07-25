from datetime import UTC, date, datetime

from ai_news.email_builder import build_digest_email, deterministic_message_id
from ai_news.models import Article, DigestEntry


def entry() -> DigestEntry:
    article = Article(
        article_id="a",
        source_name="Source <script>",
        source_priority=80,
        is_official_source=True,
        title="Model <X> & GPU",
        url_original="https://example.com/a",
        url_canonical="https://example.com/a",
        published_at_utc=datetime(2026, 7, 25, tzinfo=UTC),
    )
    return DigestEntry(
        article=article,
        summary_es="Resumen <seguro>",
        why_it_matters="Importa & mucho",
    )


def test_multipart_email_contains_text_and_html_with_escaping() -> None:
    message = build_digest_email(
        [entry()],
        digest_date=date(2026, 7, 25),
        sender="sender@example.com",
        recipient="reader@example.com",
        repository="owner/repo",
    )
    assert message.is_multipart()
    plain = message.get_body(preferencelist=("plain",)).get_content()
    html = message.get_body(preferencelist=("html",)).get_content()
    assert "Model <X> & GPU" in plain
    assert "Model &lt;X&gt; &amp; GPU" in html
    assert "<script>" not in html


def test_empty_digest_is_still_rendered() -> None:
    message = build_digest_email(
        [],
        digest_date=date(2026, 7, 25),
        sender="sender@example.com",
        recipient="reader@example.com",
        repository="owner/repo",
    )
    assert "No hubo novedades" in message.get_body(preferencelist=("plain",)).get_content()


def test_message_id_is_deterministic() -> None:
    value = deterministic_message_id(date(2026, 7, 25), "owner/repo", "Reader@example.com")
    assert value == deterministic_message_id(date(2026, 7, 25), "owner/repo", "reader@example.com")
