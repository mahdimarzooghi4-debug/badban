from __future__ import annotations

import structlog

from badban.config import Settings
from badban.observability import configure_logging


def test_sensitive_structured_fields_are_redacted(settings: Settings, capsys) -> None:
    configure_logging(settings)
    structlog.get_logger("test").info(
        "provider_check",
        provider_id="provider-test",
        api_token="do-not-print-this-value",
    )
    output = capsys.readouterr().out
    assert "do-not-print-this-value" not in output
    assert "[REDACTED]" in output
