@echo off
cd /d "%~dp0"
echo Stopping old Antimony API servers on port 8765...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /R /C:":8765 .*LISTENING"') do taskkill /PID %%p /F >nul 2>nul
timeout /t 1 /nobreak >nul
start "" assistant_web.html
"C:\Users\sreen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" anime_ml_assistant.py --api
pause
