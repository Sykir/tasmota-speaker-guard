@echo off
cd /d "%~dp0"
echo Arret de Tasmota Speaker Guard...
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*speaker_guard*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo Extinction des enceintes Tasmota...
python speaker_guard.py off
echo Termine.
pause
