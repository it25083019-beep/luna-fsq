# Roadmap — toward the finished LUNA app

Character: **2D sprites now**. 3D / Live2D later (do not block).

## Now (usable)

| Surface | Status |
|---------|--------|
| Web app `/app` | **5-tab FSQ shell** — Home / Chat / Quest map / Career / My Page (design-demo aligned) |
| Web `/login` | Shared login + admin App vs Admin picker |
| Admin `/admin` | User list, reset password (opt-in only) |
| Theme settings | My Page — FSQ Night default + pastel presets |
| Flutter `luna_flutter/` | Source ready; needs Flutter SDK install |

## Test flow (Render)

1. https://luna-fsq.onrender.com/login — log in  
2. Admin: choose **アプリへ** (not forced into admin)  
3. https://luna-fsq.onrender.com/app — switch bottom tabs  
4. Chat tab: LUNA dialogue + life modules overlay  
5. My Page: theme, voice, admin link (admin only)

Local: http://127.0.0.1:8006/app

## Next

1. Flutter SDK → run `luna_flutter/` on phone  
2. SMTP on Render for forgot-password email  
3. Push notifications  
4. Illustrated map assets (replace CSS map strip)  
5. Live2D / 3D when art is ready

## Design reference

Mockups: [`docs/design-demo/`](design-demo/)
