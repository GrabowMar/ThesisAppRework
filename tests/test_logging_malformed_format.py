import logging
from app.utils.logging_config import setup_application_logging

def test_malformed_logging_format_does_not_raise(caplog):
    """Ensure malformed printf-style logging calls are normalized and not crashing.

    We intentionally pass fewer args than format placeholders expect. Our
    _safe_get_message helper should catch the TypeError and normalize the
    record so downstream formatters/filters proceed without error.
    """
    logger = setup_application_logging()
    with caplog.at_level(logging.INFO):
        # Malformed: two placeholders, one arg
        logger.info("User %s performed %s action", "alice")  # noqa: F541
        # Another malformed: placeholder with non-matching type
        logger.info("Processed item %d", "not-an-int")  # noqa: F541

    # We expect at least two records captured without raising.
    messages = [rec.getMessage() for rec in caplog.records]
    assert any("User" in m for m in messages)
    assert any("Processed item" in m for m in messages)
