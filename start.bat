@echo off
cd /d "%~dp0"
echo Stopping existing instances...
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*speaker_guard*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
echo Starting Tasmota Speaker Guard in background...
start "" pythonw.exe speaker_guard.pyw
echo Service started. Check speaker_guard.log for details.
pause
