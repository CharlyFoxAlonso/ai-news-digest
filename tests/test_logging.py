from ai_news.logging_setup import redact_sensitive


def test_redacts_secret_like_fields() -> None:
    result = redact_sensitive(
        None,
        "",
        {"api_key": "secret", "Authorization": "bearer", "nested": {"token": "x"}, "safe": 1},
    )
    assert result == {
        "api_key": "[REDACTED]",
        "Authorization": "[REDACTED]",
        "nested": {"token": "[REDACTED]"},
        "safe": 1,
    }
