from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.models.session import CheckOutMethod, SessionStatus
from app.services.checkout import calculate_duration_minutes, close_session


def make_session(*, status: SessionStatus = SessionStatus.open):
    check_in_at = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
    return SimpleNamespace(
        id="session-1",
        status=status,
        check_in_at=check_in_at,
        check_out_at=None,
        check_out_method=None,
        duration_minutes=None,
        flag_reason=None,
    )


def test_calculate_duration_minutes_floors_partial_minutes() -> None:
    start = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
    end = start + timedelta(minutes=42, seconds=59)

    assert calculate_duration_minutes(start, end) == 42


def test_calculate_duration_minutes_never_goes_negative() -> None:
    start = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)

    assert calculate_duration_minutes(start, start - timedelta(minutes=5)) == 0


def test_close_session_sets_checkout_fields() -> None:
    session = make_session()
    checkout_at = session.check_in_at + timedelta(minutes=75)

    close_session(session, CheckOutMethod.qr, checkout_at)

    assert session.check_out_at == checkout_at
    assert session.check_out_method is CheckOutMethod.qr
    assert session.status is SessionStatus.closed
    assert session.duration_minutes == 75
    assert session.flag_reason is None


def test_close_session_flags_when_reason_is_provided() -> None:
    session = make_session()
    checkout_at = session.check_in_at + timedelta(minutes=15)

    close_session(
        session,
        CheckOutMethod.auto_timeout,
        checkout_at,
        flag_reason="Session exceeded automatic timeout",
    )

    assert session.status is SessionStatus.flagged
    assert session.flag_reason == "Session exceeded automatic timeout"
    assert session.duration_minutes == 15


def test_close_session_rejects_non_open_session() -> None:
    session = make_session(status=SessionStatus.closed)

    with pytest.raises(ValueError, match="expected 'open'"):
        close_session(
            session,
            CheckOutMethod.admin,
            session.check_in_at + timedelta(minutes=10),
        )
