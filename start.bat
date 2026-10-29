@echo off
cd /d "%~dp0"
echo Arret des instances existantes...
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*speaker_guard*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
echo Demarrage de Tasmota Speaker Guard en arriere-plan...
start "" pythonw.exe speaker_guard.pyw
echo Service demarre. Consultez speaker_guard.log pour les logs.
pause
