# LUNA 3D — Integration Guide

## Quick test

1. Artist delivers `luna-static.glb`
2. Copy to `my-project/static/luna-3d/luna-static.glb`
3. Run app → login → open **http://127.0.0.1:8006/luna-3d**
4. Drag to rotate, scroll to zoom

## File layout

```
static/luna-3d/
  luna-static.glb      # ← deliverable (not in repo until artist provides)
  references/          # turnaround PNGs for artist
  README.md
static/luna-3d-demo.html
```

## Web viewer

Route: `GET /luna-3d` → `luna-3d-demo.html`

Uses Three.js r128 + `GLTFLoader` + `OrbitControls` from CDN.

Model URL in page:

```js
const MODEL_URL = "/static/luna-3d/luna-static.glb";
```

If the file is missing, the page shows reference images and the brief link.

## Auth

Same as `/demo`: redirects to `/login?next=/luna-3d` when not logged in.

## Flutter (later)

```dart
WebView(initialUrl: 'https://luna-fsq.onrender.com/luna-3d?token=...')
```

Or use `model_viewer_plus` / `flutter_3d_controller` with the same `.glb` URL:

```
https://luna-fsq.onrender.com/static/luna-3d/luna-static.glb
```

## Performance tips

- Prefer **Draco-compressed** glb if > 2 MB
- Single draw call material when possible
- Bake AO if needed; avoid 4K textures on mobile

## Phase 2 (optional)

| Feature | Approach |
|---------|----------|
| Idle rotation | Already in viewer |
| Lip-sync | Keep 2D sprites or morph targets |
| Full rig | VRM / separate rigged glb |
| AR | `model-viewer` web component |
