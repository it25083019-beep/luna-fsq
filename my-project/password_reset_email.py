"""Optional SMTP delivery for password reset links."""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def send_password_reset_email(to_email: str, reset_url: str) -> bool:
    host = os.getenv("SMTP_HOST", "").strip()
    if not host:
        return False

    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    sender = os.getenv("SMTP_FROM", user or "noreply@luna.local")
    use_tls = os.getenv("SMTP_TLS", "true").lower() in {"1", "true", "yes"}

    msg = EmailMessage()
    msg["Subject"] = "LUNA — パスワード再設定"
    msg["From"] = sender
    msg["To"] = to_email
    msg.set_content(
        "LUNAアカウントのパスワード再設定リクエストを受け付けました。\n\n"
        f"次のリンクから新しいパスワードを設定してください（有効期限あり）:\n{reset_url}\n\n"
        "心当たりがない場合は、このメールを無視してください。"
    )

    try:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            if use_tls:
                smtp.starttls()
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)
        return True
    except Exception as exc:
        print(f"[WARN] password reset email failed: {exc}")
        return False
