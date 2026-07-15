from pathlib import Path
import json
import requests

BASE_URL = "http://127.0.0.1:8000"

# luôn lấy root theo vị trí file, không phụ thuộc đang đứng ở thư mục nào
ROOT = Path(__file__).resolve().parent.parent
TEST_CASES_FILE = ROOT / "tests" / "test_cases.json"


def load_cases():
    if TEST_CASES_FILE.exists():
        with open(TEST_CASES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    # fallback nếu chưa có file test_cases.json
    return [
        {"user_id": "u_test", "message": "Lập kế hoạch học tối nay"},
        {"user_id": "u_test", "message": "Tôi đang mất động lực"},
        {"user_id": "u_test", "message": "Gợi ý 1 việc nhỏ làm ngay bây giờ"},
    ]


def main():
    print(f"[info] root={ROOT}")
    print(f"[info] test_cases={TEST_CASES_FILE}")

    r = requests.get(f"{BASE_URL}/health", timeout=20)
    print("[health]", r.status_code, r.text)

    cases = load_cases()
    passed = 0

    for i, c in enumerate(cases, 1):
        resp = requests.post(f"{BASE_URL}/chat", json=c, timeout=90)
        if resp.status_code != 200:
            print(f"[{i}] FAIL status={resp.status_code} body={resp.text}")
            continue

        data = resp.json()
        dialogue = data.get("dialogue")
        game_state = data.get("game_state")

        if isinstance(dialogue, str) and isinstance(game_state, dict):
            print(f"[{i}] PASS")
            passed += 1
        else:
            print(f"[{i}] FAIL invalid response format: {data}")

    print(f"\nFINAL: {passed}/{len(cases)} PASS")


if __name__ == "__main__":
    main()