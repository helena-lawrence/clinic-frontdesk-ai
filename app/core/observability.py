"""Safe structured telemetry for the Clinic Front-Desk AI local demo.

Emits JSON lines to stdout. No patient IDs, user questions, model replies,
tokens, request bodies, tool arguments or tool output are recorded.
"""

import contextvars
import functools
import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone

_TRACE_ID = contextvars.ContextVar("clinic_trace_id", default=None)
_log = logging.getLogger("clinic.observability")
_log.setLevel(logging.INFO)
_log.propagate = False
if not _log.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _log.addHandler(_handler)


def record_event(
    component: str,
    operation: str,
    status: str,
    *,
    duration_ms: float | None = None,
    dependency: str | None = None,
    model: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    error_type: str | None = None,
) -> None:
    """Log only fixed, technical metadata passed explicitly by our code."""
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "dependency_span",
        "trace_id": _TRACE_ID.get() or uuid.uuid4().hex,
        "component": component,
        "operation": operation,
        "status": status,
    }
    if duration_ms is not None:
        event["duration_ms"] = round(float(duration_ms), 2)
    if dependency is not None:
        event["dependency"] = dependency
    if model is not None:
        event["model"] = model
    if input_tokens is not None:
        event["input_tokens"] = int(input_tokens)
    if output_tokens is not None:
        event["output_tokens"] = int(output_tokens)
    if error_type is not None:
        event["error_type"] = error_type
    _log.info(json.dumps(event, separators=(",", ":")))


def trace_agent(func):
    """Give all dependency events within one ask_agent call a trace ID."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        token = _TRACE_ID.set(uuid.uuid4().hex)
        started = time.perf_counter()
        status = "success"
        error_type = None
        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            status = "error"
            error_type = type(exc).__name__
            raise
        finally:
            record_event(
                "agent", "workflow", status,
                duration_ms=(time.perf_counter() - started) * 1000,
                error_type=error_type,
            )
            _TRACE_ID.reset(token)
    return wrapper
