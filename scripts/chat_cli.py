import argparse
import sys

import requests

BASE_URL = "http://127.0.0.1:8005"


def fetch_brain_hint(user_id: str, headers: dict) -> str:
    try:
        r = requests.get(f"{BASE_URL}/brain/me", headers=headers, timeout=10)
        if r.status_code != 200:
            # admin compat path
            r = requests.get(f"{BASE_URL}/brain/{user_id}", headers=headers, timeout=10)
        if r.status_code != 200:
            return ""
        data = r.json()
        mode = data.get("mode", "?")
        companion = data.get("companion_name") or "(not set)"
        uname = data.get("user_display_name") or "(not set)"
        core_k = data.get("core_trained_knowledge_count", 0)
        return f"[brain] mode={mode} user={uname} companion={companion} core_knowledge={core_k}"
    except Exception:
        return ""


def print_reply(label: str, dialogue: str, user_id: str, headers: dict) -> None:
    print(f"\n[{label}]: {dialogue}\n")
    hint = fetch_brain_hint(user_id, headers)
    if hint:
        print(hint + "\n")


def login(email: str, password: str) -> dict:
    r = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    if r.status_code != 200:
        raise SystemExit(f"Login failed ({r.status_code}): {r.text}")
    return r.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="LUNA local chat CLI")
    parser.add_argument("--user-id", default=None, help="Optional user_id override (admin only)")
    parser.add_argument("--email", default=None, help="Login email")
    parser.add_argument("--password", default=None, help="Login password")
    parser.add_argument("--port", type=int, default=8005, help="API port")
    args = parser.parse_args()

    global BASE_URL
    BASE_URL = f"http://127.0.0.1:{args.port}"

    headers = {}
    user_id = args.user_id or "admin_root"

    if args.email and args.password:
        tok = login(args.email, args.password)
        headers = {"Authorization": f"Bearer {tok['access_token']}"}
        user_id = tok.get("user_id") or user_id
        print(f"Logged in as {tok.get('email')} (user_id={user_id}, admin={tok.get('is_admin')})")
    elif args.email or args.password:
        raise SystemExit("Provide both --email and --password")
    else:
        print("Warning: no --email/--password; authenticated routes will fail.")
        print("Example: python scripts/chat_cli.py --email admin@luna.local --password admin123456")

    print("LUNA local CLI")
    print(f"user_id={user_id}")
    hint = fetch_brain_hint(user_id, headers)
    if hint:
        print(hint)
    print("Type 'exit' to quit.\n")

    if user_id != "admin_root":
        try:
            body = {"message": ""}
            if args.user_id:
                body["user_id"] = args.user_id
            r = requests.post(
                f"{BASE_URL}/chat/start",
                json=body,
                headers=headers,
                timeout=60,
            )
            if r.status_code == 200:
                print_reply("Companion", r.json().get("dialogue", ""), user_id, headers)
            else:
                print(f"Start greeting failed ({r.status_code}): {r.text}")
        except Exception as e:
            print(f"Start greeting error: {e}")

    while True:
        try:
            label = "Admin" if user_id == "admin_root" else user_id
            user_msg = input(f"[{label}]: ")
            if user_msg.lower() == "exit":
                print("Bye.")
                break
            if not user_msg.strip():
                continue

            body = {"message": user_msg}
            if args.user_id:
                body["user_id"] = args.user_id
            response = requests.post(
                f"{BASE_URL}/chat",
                json=body,
                headers=headers,
                timeout=120,
            )

            if response.status_code == 200:
                res_data = response.json()
                bot = "LUNA" if user_id == "admin_root" else "Companion"
                print_reply(bot, res_data.get("dialogue", ""), user_id, headers)
            else:
                print(f"Server error ({response.status_code}): {response.text}")
        except KeyboardInterrupt:
            print("\nBye.")
            sys.exit(0)
        except Exception as e:
            print(f"Connection error: {e}")


if __name__ == "__main__":
    main()
