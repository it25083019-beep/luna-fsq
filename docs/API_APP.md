# LUNA API — App Integration Guide

Base URL (production): `https://luna-fsq.onrender.com`  
Local: `http://127.0.0.1:8006`

All protected routes need header:
```
Authorization: Bearer <access_token>
```

---

## Auth

### POST `/auth/register`
```json
{ "email": "user@example.com", "password": "secret12", "display_name": "optional" }
```
Response → `TokenResponse`: `access_token`, `user_id`, `email`, `is_admin`

### POST `/auth/login`
```json
{ "email": "user@example.com", "password": "secret12" }
```
Same response. Errors: `401` invalid, `403` locked.

### GET `/auth/me`
Returns `{ user_id, email, display_name, is_admin }`

---

## Chat

### POST `/chat/start`
```json
{ "message": "" }
```
AI greets / continues onboarding.

### POST `/chat`
```json
{ "message": "今日は少し疲れています" }
```

### ChatResponse
```json
{
  "dialogue": "……",
  "game_state": { "...rpg/profile fields..." },
  "suggested_replies": ["体調を相談したい", "..."],
  "allow_custom_input": true,
  "allow_voice_input": true
}
```

Quota errors → HTTP `429` with:
```json
{ "detail": { "message": "...", "code": "quota_exceeded", "retry_after_seconds": 30 } }
```

---

## Profile / State

### GET `/state/me` — EXP, level, streak, history snapshot  
### GET `/brain/me` — mode (admin / companion), onboarding flags  
### POST `/user/set-name`
```json
{ "companion_name": "ミカ", "user_display_name": "太郎" }
```

### POST `/checkin/morning` — `{ "goal": "..." }`  
### POST `/checkin/evening` — `{}`

---

## Admin (is_admin only)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/admin/users` | List users |
| POST | `/admin/users/{user_id}/reset-password` | `{ "new_password": "..." }` |
| POST | `/admin/users/{user_id}/lock` | `{ "locked": true/false }` |
| GET | `/admin/export` | Full JSON backup |

UI: `https://luna-fsq.onrender.com/admin`

---

## Flutter / app checklist

1. Store `access_token` securely after login/register  
2. Attach Bearer on every chat/profile call  
3. Render `dialogue` + tap `suggested_replies`  
4. Allow free text + optional STT  
5. On `429`, show retry countdown from `retry_after_seconds`
