# LUNA Avatar / Live2D Trial

## Try now
- Local: `http://127.0.0.1:8006/live2d`
- Production: `https://luna-fsq.onrender.com/live2d`

## Current demo (sprite expressions)

Until the real Live2D PSD is ready, `/live2d` uses **LUNA expression sprites** (hair + hoodie colors match `static/live2d/luna-reference.png`):

| File | Situation |
|------|-----------|
| `luna-neutral.png` | Idle default |
| `luna-blink.png` | Auto blink every 3–6s |
| `luna-talk.png` | Lip-sync while TTS speaks |
| `luna-wave.png` | Greeting / first chat |
| `luna-cheer.png` | Encouragement (がんばって, すごい, etc.) |
| `luna-happy.png` | Positive / tap on character |
| `luna-think.png` | Questions / user thinking |
| `luna-sad.png` | Sympathy / tough topics |
| `luna-surprised.png` | Surprise reactions |

Logic: `static/live2d/luna-avatar.js` — keyword detection on Japanese dialogue + manual test buttons.

## Replace with real Live2D model

### Artist deliverables (required)
1. **PSD with layers** (not flat PNG):
   - hair front/back, face, eyes (open/closed), eyebrows, mouth open/closed/smile, body, arms, hoodie, notebook
   - motions: idle, wave, cheer, tap
2. Same pose angle as reference (front or 3/4)
3. Export from **Live2D Cubism Editor** as `.model3.json` + textures folder

### Put files here
```
my-project/static/live2d/luna/
  luna.model3.json
  textures/...
```

### Wire into demo
Restore pixi-live2d in `live2d-demo.html` and set:
```js
const MODEL_URL = "/static/live2d/luna/luna.model3.json";
```
Map chat events to Live2D expressions/motions (same rules as `luna-avatar.js`).

## Notes
- AI-generated sprites are a **placeholder** — not pixel-perfect across all poses
- 1 static PNG cannot become Live2D — need layered PSD + Cubism Editor
- For better lip-sync later: pre-render voice (TTS API) + `model.speak(audioUrl)`
- Flutter: use WebView for this page first, or Live2D Flutter plugin later
