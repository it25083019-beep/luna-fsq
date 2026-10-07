# -*- coding: utf-8 -*-
"""Login lock, token version, sealed phones, calendar HTML escape."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pydantic import ValidationError

from auth_security import (
    LOGIN_MAX_FAILS,
    clear_login_throttle,
    create_access_token,
    decode_access_token,
    login_throttled,
    record_login_failure,
    record_login_success,
    token_version_matches,
)
from privacy_vault import sanitize_admin_export_brain, seal_brain_for_storage, unseal_brain_after_load
from schemas import ChangePasswordRequest, RegisterRequest, ResetPasswordRequest


class _User:
    def __init__(self) -> None:
        self.token_version = 0
        self.login_fail_count = 0
        self.login_locked_until = None
        self.email = "lock@example.com"


def test_new_password_minimum_is_ten():
    RegisterRequest(email="a@b.co", password="1234567890")
    ChangePasswordRequest(current_password="old-pass", new_password="1234567890")
    ResetPasswordRequest(token="x" * 20, new_password="1234567890")
    for model, kwargs in (
        (RegisterRequest, {"email": "a@b.co", "password": "123456789"}),
        (ChangePasswordRequest, {"current_password": "old", "new_password": "123456789"}),
        (ResetPasswordRequest, {"token": "x" * 20, "new_password": "123456789"}),
    ):
        try:
            model(**kwargs)
        except ValidationError:
            continue
        raise AssertionError(model.__name__)
    print("OK password length 10")


def test_login_locks_after_repeated_failures():
    clear_login_throttle()
    email = "lock-test@example.com"
    user = _User()
    for _ in range(LOGIN_MAX_FAILS - 1):
        record_login_failure(email, user)
        assert not login_throttled(email, user)
    record_login_failure(email, user)
    assert user.login_fail_count == LOGIN_MAX_FAILS
    assert user.login_locked_until is not None
    assert login_throttled(email, user)
    record_login_success(email, user)
    assert user.login_fail_count == 0
    assert user.login_locked_until is None
    assert not login_throttled(email, user)
    ghost = "missing-lock@example.com"
    for _ in range(LOGIN_MAX_FAILS):
        record_login_failure(ghost, None)
    assert login_throttled(ghost, None)
    clear_login_throttle()
    print("OK login lock")


def test_token_version_rejects_old_jwt():
    user = _User()
    user.token_version = 2
    token = create_access_token("abc", extra={"tv": 99}, token_version=2)
    payload = decode_access_token(token)
    assert payload["tv"] == 2
    assert token_version_matches(payload, user)
    user.token_version = 3
    assert not token_version_matches(payload, user)
    legacy = decode_access_token(
        create_access_token("abc", token_version=0)
    )
    user.token_version = 0
    assert token_version_matches(legacy, user)
    print("OK token version")


def test_phones_and_mail_sealed_and_export_drops_them():
    brain = {
        "mail_link": {"access_token": "ya29-secret", "refresh_token": "1//refresh"},
        "emergency_contacts": [{"id": "c1", "name": "お母さん", "tel": "09012345678", "relation": "family"}],
        "chat_history": [],
    }
    seal_brain_for_storage(brain)
    tel = brain["emergency_contacts"][0]["tel"]
    name = brain["emergency_contacts"][0]["name"]
    assert tel.startswith("luna1:")
    assert "09012345678" not in tel
    assert name.startswith("luna1:")
    assert brain["mail_link"]["access_token"].startswith("luna1:")
    assert "ya29-secret" not in brain["mail_link"]["access_token"]
    dumped = sanitize_admin_export_brain(brain)
    assert "emergency_contacts" not in dumped
    assert "mail_link" not in dumped
    unseal_brain_after_load(brain)
    assert brain["emergency_contacts"][0]["tel"] == "09012345678"
    assert brain["emergency_contacts"][0]["name"] == "お母さん"
    assert brain["mail_link"]["refresh_token"] == "1//refresh"
    print("OK sealed contacts")


def test_db_lock_survives_without_memory():
    clear_login_throttle()
    user = _User()
    user.login_locked_until = datetime.now(timezone.utc) + timedelta(minutes=10)
    assert login_throttled("fresh-memory@example.com", user)
    user.login_locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)
    assert not login_throttled("fresh-memory@example.com", user)
    print("OK db lock window")


def test_ui_escapes_calendar_and_asks_for_ten():
    from pathlib import Path

    root = Path(__file__).resolve().parent
    js = (root / "static" / "app.js").read_text(encoding="utf-8")
    html = (root / "static" / "app.html").read_text(encoding="utf-8")
    login = (root / "static" / "login.html").read_text(encoding="utf-8")
    assert "function escHtml(" in js
    assert "escHtml(shortEventTitle(ev.title))" in js
    assert "escHtml(ev.location)" in js
    assert "新しいパスワードは10文字以上です。" in js
    assert "10文字以上" in html
    assert "パスワードは10文字以上にしてください" in login
    assert 'minlength="6"' not in login
    print("OK ui copy")


if __name__ == "__main__":
    test_new_password_minimum_is_ten()
    test_login_locks_after_repeated_failures()
    test_token_version_rejects_old_jwt()
    test_phones_and_mail_sealed_and_export_drops_them()
    test_db_lock_survives_without_memory()
    test_ui_escapes_calendar_and_asks_for_ten()
    print("ALL security hardening tests passed")
