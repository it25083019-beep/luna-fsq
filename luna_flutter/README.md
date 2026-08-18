# LUNA Flutter app

Native companion client. Uses the **same API** as the web app (`/app`).
Character is **2D sprites** for now; 3D/Live2D can replace the image later.

## This machine

Flutter SDK is **not installed yet**. Install once:

1. https://docs.flutter.dev/get-started/install/windows
2. Restart the terminal
3. In this folder:

```powershell
cd D:\usbreco\my-project\luna_flutter
flutter create . --project-name luna_flutter --org jp.fsq.luna
flutter pub get
flutter run
```

`flutter create .` generates Android/iOS folders without overwriting `lib/`.

## API

Default: `https://luna-fsq.onrender.com`

Local backend (Windows desktop):

```powershell
flutter run --dart-define=LUNA_API=http://127.0.0.1:8006
```

Android emulator:

```powershell
flutter run --dart-define=LUNA_API=http://10.0.2.2:8006
```

## What v0.1 includes

- Shared login / register
- Chat + suggested chips
- EXP/level from `/state/me`
- 2D LUNA sprite from production static files

## Later

- Push notifications
- Forgot-password screen
- Swap sprite for Live2D / `.glb`
