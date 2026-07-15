# Admin & Backup

## Admin panel
Open: `/admin`  
Login with admin account (`ADMIN_EMAIL` / `ADMIN_PASSWORD` on Render).

## Export before Postgres Free expires (~30 days)
1. Admin panel → **バックアップJSON**, or  
2. CLI:
```powershell
cd D:\usbreco\my-project
.venv\Scripts\python.exe scripts\export_backup.py --email YOUR_ADMIN --password YOUR_PASS --out luna-backup.json
```

Keep the JSON somewhere safe (Drive / PC). When upgrading to paid Postgres or new DB, we can restore from this file.
