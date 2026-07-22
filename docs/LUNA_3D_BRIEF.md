# LUNA — Static 3D Model Brief (FSQ)

**Project:** Future Skill Quest (FSQ) — AI companion app  
**Character:** LUNA (user-facing companion; chibi anime girl)  
**Deliverable:** **1 static 3D model** (no rig required for v1)  
**Format:** `.glb` (preferred) or `.fbx` + textures  
**Reference images:** `my-project/static/luna-3d/references/`

---

## 1. Character summary

| Item | Spec |
|------|------|
| Style | Chibi anime, soft pastel, clean outlines |
| Age look | Teen / young student |
| Hair | Long straight **lavender / light purple**, bangs, **ahoge** (cowlick) on top-left |
| Hair accessory | Small **pink 5-petal flower** clip on right side |
| Eyes | Large purple, simple lashes, white highlights |
| Outfit | **White hoodie** + **purple hood/collar** (oversized) |
| Prop | **Pink spiral notebook** held with both hands at chest |
| Cheeks | Light pink blush marks |
| Pose (v1) | **Front neutral standing**, feet on ground, notebook at chest (match `luna-ref-original.png`) |

---

## 2. Reference image list

| File | View |
|------|------|
| `luna-ref-original.png` | **Canonical front** (approved design) |
| `luna-ref-front.png` | Front (modeling pose) |
| `luna-ref-side-left.png` | Left profile |
| `luna-ref-side-right.png` | Right profile |
| `luna-ref-back.png` | Back |
| `luna-ref-3quarter-left.png` | 3/4 front-left |
| `luna-ref-3quarter-right.png` | 3/4 front-right |
| `luna-ref-details.png` | Face / props detail sheet |

> AI-generated turnarounds are **guide only** — match `luna-ref-original.png` for colors and proportions.

---

## 3. Color palette (approximate)

| Part | Hex | Note |
|------|-----|------|
| Hair | `#C8B6E8` ~ `#D4C4F0` | Lavender |
| Hoodie body | `#F5F5F5` ~ `#FFFFFF` | Off-white |
| Hood / collar | `#7B5EA7` ~ `#6B4E9A` | Purple |
| Eyes | `#7B5EA7` | Match hoodie purple |
| Flower clip | `#F5A8C8` | Pink |
| Notebook cover | `#F8B4C8` | Pink |
| Blush | `#F0A0B0` | Soft pink |
| Skin | `#FFE8E0` | Fair, warm |

---

## 4. Technical requirements

### Mesh
- **Static only** (no skeleton required for v1)
- Target: **5k–15k tris** (mobile-friendly)
- Single material or few materials (hair / skin / clothes / book)
- Origin at **feet center**, facing **+Z** (or document your axis)
- Scale: ~**1.4 m** height in world units (chibi proportions)

### Textures
- PBR or toon/cel-shade OK (prefer **soft toon** to match 2D art)
- 1024×1024 or 2048×2048 atlas
- Include **base color**; normal map optional

### Export
```
my-project/static/luna-3d/
  luna-static.glb    ← main deliverable
  textures/          ← if separate (embed in glb preferred)
```

### Naming in scene
- Root node: `Luna` or `luna_root`
- Optional separate mesh: `notebook` (can be merged)

---

## 5. Out of scope (v1)

- Rigging / bones
- Blend shapes / facial animation
- Live2D layers
- Alternate costumes

*(Rig + expressions can be phase 2.)*

---

## 6. Acceptance checklist

- [ ] Silhouette matches reference front view
- [ ] Hair color, hoodie white/purple, pink flower & notebook correct
- [ ] Ahoge present and readable from front/3/4
- [ ] Loads in Three.js `GLTFLoader` without errors
- [ ] File size **< 5 MB** (compressed glb)
- [ ] No inverted normals; clean UVs

---

## 7. Integration (for dev)

After delivery, place file at:

```
static/luna-3d/luna-static.glb
```

Open demo: `/luna-3d` (login required, same as `/demo`)

See `docs/LUNA_3D_INTEGRATION.md` for viewer code and Flutter/WebView notes.

---

## 8. 日本語サマリー（モデラー向け）

**キャラ名:** LUNA（ちびキャラAIコンパニオン）  
**納品:** 静的3Dモデル1体（`.glb`推奨）  
**ポーズ:** 正面立ち、胸元でピンクのノートを両手で持つ  
**髪:** 薄紫ロング、あほ毛、右側にピンクの花クリップ  
**服:** 白パーカー＋紫フード／襟  
**参考:** `static/luna-3d/references/luna-ref-original.png` が正  
**配置:** `static/luna-3d/luna-static.glb`  
**確認:** `/luna-3d` で表示テスト

---

## Contact / repo

- GitHub: https://github.com/it25083019-beep/luna-fsq  
- 2D expression sprites (interim): `static/live2d/luna-expressions/`
