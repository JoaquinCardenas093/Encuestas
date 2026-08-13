"""Per-request session identity (no auth). Set from the X-Session-Id header."""
import contextvars
import re

_current_session: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "aurum_session", default=None
)
_VALID = re.compile(r"^[A-Za-z0-9-]{1,64}$")


def set_session(sid: str | None) -> None:
    _current_session.set(sid)


def get_session() -> str | None:
    return _current_session.get()


def safe_session_id(raw: str | None) -> str | None:
    if raw and _VALID.match(raw):
        return raw
    return None
