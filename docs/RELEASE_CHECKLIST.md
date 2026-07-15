# Release Checklist

## Env
- [ ] GOOGLE_API_KEY set
- [ ] MODEL_NAME set

## API
- [ ] GET /health ok
- [ ] GET /state/{user_id} ok
- [ ] POST /checkin/morning ok
- [ ] POST /checkin/evening ok
- [ ] POST /chat ok

## Logic
- [ ] EXP increases correctly
- [ ] daily cap works
- [ ] level updates correctly

## AI
- [ ] dialogue returned
- [ ] game_state returned
- [ ] no crash on malformed AI output

## Demo
- [ ] demo script run end-to-end
- [ ] video capture ready