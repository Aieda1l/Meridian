"""Session checkout central utility."""

from datetime import datetime
from app.models.session import Session, CheckOutMethod, SessionStatus

def calculate_duration_minutes(check_in_at: datetime, check_out_at: datetime) -> int:
    """Return the duration in whole minutes between two timestamps."""
    delta = (check_out_at - check_in_at).total_seconds()
    return max(int(delta // 60), 0)

def close_session(session: Session, method: CheckOutMethod, checkout_at: datetime, *, flag_reason: str | None = None) -> None:
    """Consistently transition an open session to closed status."""
    if session.status != SessionStatus.open:
        raise ValueError(
            f"Cannot close session {session.id}: status is {session.status!r}, expected 'open'"
        )
    session.check_out_at = checkout_at
    session.check_out_method = method
    session.status = SessionStatus.flagged if flag_reason else SessionStatus.closed
    if flag_reason:
        session.flag_reason = flag_reason
    session.duration_minutes = calculate_duration_minutes(session.check_in_at, checkout_at)
