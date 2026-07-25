from pathlib import Path

import yaml


def test_workflow_yaml_and_required_crons() -> None:
    root = Path(__file__).parents[1]
    daily_text = (root / ".github/workflows/daily.yml").read_text(encoding="utf-8")
    ci_text = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert yaml.safe_load(daily_text)
    assert yaml.safe_load(ci_text)
    assert 'cron: "45 11 * * *"' in daily_text
    assert 'cron: "15 12 * * *"' in daily_text
    assert "cancel-in-progress: false" in daily_text
    assert "uv run pytest --cov=ai_news" in ci_text
