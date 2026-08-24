# Roadmap — toward the finished LUNA app

Character: **2D sprites now**. 3D / Live2D later (do not block).

## Now (usable)

| Surface | Status |
|---------|--------|
| Web app `/app` | Login → 2D LUNA + chat + check-in + life modules |
| Web `/login` | Shared admin/user gate |
| Admin `/admin` | User list, reset password |
| Theme settings | `/app` → 設定 — lilac / mint / peach / sky / night (saved locally, also on login) |
| Flutter `luna_flutter/` | Source ready; needs Flutter SDK install |

## Next

1. Install Flutter SDK → `flutter create .` in `luna_flutter/` → run on phone
2. SMTP on Render (`SMTP_HOST` …) so forgot-password emails work in production
3. Push notifications (Flutter + backend)
4. Deeper life calculators (wage / sleep streak / calendar sync)
5. Artist Live2D PSD or static `.glb` → drop into existing viewers

## URLs

- Production app: https://luna-fsq.onrender.com/app
- Login: https://luna-fsq.onrender.com/login
- Local: http://127.0.0.1:8006/app
