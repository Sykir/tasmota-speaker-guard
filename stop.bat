@echo off
cd /d "%~dp0"
echo Stopping Tasmota Speaker Guard...
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*speaker_guard*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo Turning OFF Tasmota plugs...
python speaker_guard.py off
echo Done.
pause
