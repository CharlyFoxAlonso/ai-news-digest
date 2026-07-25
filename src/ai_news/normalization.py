import hashlib
import html
import re
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ai_news.feed_parser import ParsedFeedItem
from ai_news.models import Article

TRACKING_PARAMETERS = {
    "fbclid",
    "gclid",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}
MAX_TITLE_LENGTH = 240
MAX_DESCRIPTION_LENGTH = 1_500


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def clean_html(value: str, max_length: int = MAX_DESCRIPTION_LENGTH) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    text = html.unescape(" ".join(parser.parts))
    return normalize_whitespace(text)[:max_length].rstrip()


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_title(value: str) -> str:
    return normalize_whitespace(html.unescape(value))[:MAX_TITLE_LENGTH].rstrip()


def canonicalize_url(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ValueError("URL must use HTTP(S) and include a hostname")
    scheme = parts.scheme.lower()
    hostname = parts.hostname.lower()
    port = parts.port
    netloc = hostname if port is None else f"{hostname}:{port}"
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")
    query = sorted(
        (key, val)
        for key, val in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMETERS
    )
    return urlunsplit((scheme, netloc, path, urlencode(query, doseq=True), ""))


def article_from_feed(item: ParsedFeedItem) -> Article | None:
    if item.published_at_utc is None:
        return None
    canonical = canonicalize_url(str(item.url))
    title = normalize_title(item.title)
    identifier = hashlib.sha256(f"{canonical}\n{title.casefold()}".encode()).hexdigest()[:24]
    return Article(
        article_id=identifier,
        source_name=item.source.name,
        source_priority=item.source.priority,
        is_official_source=item.source.is_official,
        title=title,
        url_original=item.url,
        url_canonical=canonical,
        published_at_utc=item.published_at_utc,
        description=clean_html(item.description),
        category=normalize_whitespace(item.category) or "other",
    )
