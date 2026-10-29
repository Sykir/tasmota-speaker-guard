# Tasmota Speaker Guard - Windows Uninstaller

$TaskName = "TasmotaSpeakerGuard"
$StartupDir = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $StartupDir "TasmotaSpeakerGuard.lnk"

Write-Host "Stopping running processes..." -ForegroundColor Yellow
Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*speaker_guard*" } | Stop-Process -Force -ErrorAction SilentlyContinue

$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($Task) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "[OK] Scheduled Task '$TaskName' removed." -ForegroundColor Green
}

if (Test-Path $ShortcutPath) {
    Remove-Item $ShortcutPath -Force
    Write-Host "[OK] Startup shortcut removed." -ForegroundColor Green
}

Write-Host "Uninstallation complete." -ForegroundColor Cyan
