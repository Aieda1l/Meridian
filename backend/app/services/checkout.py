"""Session checkout central utility."""

from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.session import Session, CheckOutMethod, SessionStatus

def _calculate_duration_minutes(check_in_at: datetime, check_out_at: datetime) -> int:
    """Return the duration in whole minutes between two timestamps."""
    delta = (check_out_at - check_in_at).total_seconds()
    return max(int(delta // 60), 0)

def close_session(session: Session, method: CheckOutMethod, checkout_at: datetime) -> None:
    """Consistently transition an open session to closed status."""
    session.check_out_at = checkout_at
    session.check_out_method = method
    session.status = SessionStatus.closed
    session.duration_minutes = _calculate_duration_minutes(session.check_in_at, checkout_at)
