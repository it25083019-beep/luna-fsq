# Life modules (健康 / お金 / スケジュール)

## Idea
First-meeting **~14 questions are only a baseline**.
After that, the user can **add more anytime** in three modules:

| Module | API | UI tab on `/app` |
|--------|-----|------------------|
| health | `GET/POST /life/health` | 健康 |
| money | `GET/POST /life/money` | お金 |
| schedule | `GET/POST /life/schedule` | スケジュール |

## Append note
```http
POST /life/money
Authorization: Bearer …
Content-Type: application/json

{ "note": "時給1200円・週3・欲しいイヤホン10000円" }
```

Optional `structured` JSON for future calculators (wage, wishlist price, etc.).

## 2D avatar (Open-LLM-VTuber patterns)
- `emotionMap`: `[joy]` / `game_state.emotion` → sprite
- Idle bob + blink
- Tap → random wave/cheer/happy
- Lip-sync while browser TTS speaks

Live2D Cubism can replace sprites later without changing the emotion tag protocol.
