"""A consult session must expire.

The flag used to be set forever, so after one tap on 「体調を相談したい」 every
later message was answered by local templates and never reached the model.
"""
from datetime import datetime, timedelta, timezone

import luna_service as ls


def _started(minutes_ago):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


def test_fresh_session_is_active():
    user = {"companion_name": "ルナ"}
    ls._begin_consult_session(user, "health")
    assert user["consult_mode"] == "health"
    assert user["consult_turns"] == 0
    assert ls._consult_session_active(user) is True


def test_session_expires_after_max_turns():
    user = {"consult_mode": "health", "consult_started_at": _started(1)}
    for _ in range(ls.CONSULT_MAX_TURNS):
        assert ls._consult_session_active(user) is True
        ls._companion_consult_followup(user, "眠れてないんだ")

    assert ls._consult_session_active(user) is False
    assert "consult_mode" not in user
    assert "consult_turns" not in user


def test_session_expires_after_ttl():
    user = {
        "consult_mode": "money",
        "consult_turns": 0,
        "consult_started_at": _started(ls.CONSULT_TTL_MINUTES + 1),
    }
    assert ls._consult_session_active(user) is False
    assert "consult_mode" not in user


def test_session_survives_within_ttl():
    user = {
        "consult_mode": "money",
        "consult_turns": 1,
        "consult_started_at": _started(ls.CONSULT_TTL_MINUTES - 5),
    }
    assert ls._consult_session_active(user) is True
    assert user["consult_mode"] == "money"


def test_naive_timestamp_is_treated_as_utc():
    naive = (datetime.now(timezone.utc) - timedelta(minutes=ls.CONSULT_TTL_MINUTES + 5))
    user = {
        "consult_mode": "health",
        "consult_turns": 0,
        "consult_started_at": naive.replace(tzinfo=None).isoformat(),
    }
    assert ls._consult_session_active(user) is False


def test_corrupt_values_do_not_crash():
    assert ls._consult_session_active({}) is False
    assert ls._consult_session_active({"consult_mode": None}) is False
    user = {"consult_mode": "health", "consult_turns": "oops", "consult_started_at": "junk"}
    assert ls._consult_session_active(user) is True


def test_legacy_session_without_timestamp_still_expires_on_turns():
    """Sessions saved before the fix have no timestamp; turns must still cap them."""
    user = {"consult_mode": "health", "consult_turns": ls.CONSULT_MAX_TURNS}
    assert ls._consult_session_active(user) is False
    assert "consult_mode" not in user
