# Live2D Trial for LUNA

## Try now
Local: `http://127.0.0.1:8006/live2d`
Production: `https://luna-fsq.onrender.com/live2d`

Uses **sample Haru model** (Live2D free material) to test:
- Canvas display
- Tap motion / expression
- Chat dialogue + browser TTS (ja-JP)
- Simple lip-sync (mouth parameter)

Your Luna design reference PNG is shown in the corner until the real model is ready.

## Replace with real Luna model

### Artist deliverables (required)
1. **PSD with layers** (not flat PNG):
   - hair front/back, face, eyes, eyebrows, mouth open/closed, body, arms, hoodie, notebook
2. Same pose angle as reference (front or 3/4)
3. Export from **Live2D Cubism Editor** as `.model3.json` + textures folder

### Put files here
```
my-project/static/live2d/luna/
  luna.model3.json
  textures/...
```

### Update demo page
In `live2d-demo.html`, change:
```js
const MODEL_URL = "/static/live2d/luna/luna.model3.json";
```

## Notes
- 1 static PNG cannot become Live2D — need layered PSD + Cubism Editor
- For better lip-sync later: pre-render voice (TTS API) + `model.speak(audioUrl)`
- Flutter: use WebView for this page first, or Live2D Flutter plugin later
