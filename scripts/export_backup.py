"""Download admin backup JSON from a running LUNA server.

Usage:
  python scripts/export_backup.py --base https://luna-fsq.onrender.com \\
    --email ADMIN_EMAIL --password ADMIN_PASSWORD --out luna-backup.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="https://luna-fsq.onrender.com")
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--out", default="luna-backup.json")
    args = p.parse_args()
    base = args.base.rstrip("/")
    login = requests.post(
        f"{base}/auth/login",
        json={"email": args.email, "password": args.password},
        timeout=60,
    )
    login.raise_for_status()
    token = login.json()["access_token"]
    if not login.json().get("is_admin"):
        raise SystemExit("Account is not admin")
    exp = requests.get(
        f"{base}/admin/export",
        headers={"Authorization": f"Bearer {token}"},
        timeout=120,
    )
    exp.raise_for_status()
    data = exp.json()
    Path(args.out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.out} users={data.get('user_count')}")


if __name__ == "__main__":
    main()
