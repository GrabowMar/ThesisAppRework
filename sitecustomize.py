"""Early logging hardening loaded automatically by Python.

Installs a defensive LogRecordFactory that prevents malformed printf-style
logging calls (mismatched placeholders / args) from raising during test
collection or very early imports before application logging config runs.

This avoids the need for monkey-patching LogRecord.getMessage globally.
"""
from __future__ import annotations
import logging

if not getattr(logging, "_thesis_site_factory", False):  # idempotent
    orig_factory = logging.getLogRecordFactory()

    class _SafeEarlyLogRecord(logging.LogRecord):  # pragma: no cover
        def getMessage(self):  # type: ignore[override]
            msg = str(self.msg)
            if self.args:
                try:
                    msg = msg % self.args
                except TypeError:
                    # Drop args; retain template so developer can see issue.
                    self.args = ()
                except Exception:
                    self.args = ()
            return msg

    def _factory(*args, **kwargs):  # pragma: no cover
        base = orig_factory(*args, **kwargs)
        safe = _SafeEarlyLogRecord(
            base.name, base.levelno, base.pathname, base.lineno,
            base.msg, base.args, base.exc_info, base.funcName,
            base.__dict__.get('sinfo')
        )
        if hasattr(base, 'stack_info'):
            try:
                safe.stack_info = base.stack_info  # type: ignore[attr-defined]
            except Exception:
                pass
        for k, v in base.__dict__.items():
            if k not in safe.__dict__:
                try:
                    setattr(safe, k, v)
                except Exception:
                    pass
        return safe

    logging.setLogRecordFactory(_factory)
    setattr(logging, "_thesis_site_factory", True)
