# -*- coding: utf-8 -*-
"""Forgot-password UI + settings password form."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_login_forgot_keeps_reset_link():
    html = (ROOT / "static" / "login.html").read_text(encoding="utf-8")
    forgot = html.split("if (forgotMode)")[1].split("if (resetMode)")[0]
    assert "setAuthMode(\"reset\")" not in forgot
    assert "data.reset_url" in forgot
    assert "ここをタップして新しいパスワードを設定" in forgot
    print("OK forgot UI no longer swallows the reset link")


def test_settings_has_password_change():
    app = (ROOT / "static" / "app.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert 'id="pwChangeBtn"' in app
    assert 'id="menuPasswordBtn"' in app
    assert "/auth/change-password" in js
    print("OK settings password change")


def test_settings_has_bug_report_mail():
    app = (ROOT / "static" / "app.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert "it25083019@tsb-yyg.ac.jp" in app
    assert 'id="supportSendBtn"' in app
    assert "mailto:" in js
    print("OK settings bug report mailto")


if __name__ == "__main__":
    test_login_forgot_keeps_reset_link()
    test_settings_has_password_change()
    test_settings_has_bug_report_mail()
    print("ALL password tests passed")
