# API Contract (MVP)

## Base URL (local)
`http://127.0.0.1:8000`

## 1) GET /health
### Response 200
```json
{"ok": true}
```

## 2) GET /state/{user_id}
### Response 200
```json
{
  "user_id": "u1",
  "current_level": 1,
  "total_exp": 0,
  "daily_exp": 0,
  "streak": 0,
  "chat_history": []
}
```

## 3) POST /checkin/morning
### Request
```json
{"user_id":"u1","goal":"hoc 2 pomodoro"}
```
### Response 200
```json
{"message":"Morning saved","exp_gain":8,"state":{}}
```

## 4) POST /checkin/evening
### Request
```json
{"user_id":"u1"}
```
### Response 200
```json
{"message":"Evening saved","exp_gain":12,"state":{}}
```

## 5) POST /chat
### Request
```json
{"user_id":"u1","message":"Lap ke hoach hoc toi nay"}
```
### Response 200
```json
{
  "dialogue":"...",
  "game_state":{
    "current_focus":"...",
    "current_plan":"...",
    "current_do_now":"...",
    "memory_note":"..."
  }
}
```

## Error format
- 400: Bad Request
- 500: Server/Model error

```json
{"detail":"..."}
```