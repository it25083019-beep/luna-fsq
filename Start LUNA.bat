@echo off
:: Double-click to start LUNA without showing a console (server runs minimized).
cd /d "%~dp0"
wscript.exe "%~dp0start-luna-hidden.vbs"
