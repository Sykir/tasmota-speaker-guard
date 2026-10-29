# Desinstallation de Tasmota Speaker Guard sous Windows

$TaskName = "TasmotaSpeakerGuard"
$StartupDir = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $StartupDir "TasmotaSpeakerGuard.lnk"

Write-Host "Arret des processus en cours..." -ForegroundColor Yellow
Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*speaker_guard*" } | Stop-Process -Force -ErrorAction SilentlyContinue

$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($Task) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "[OK] Tache planifiee '$TaskName' supprimee." -ForegroundColor Green
}

if (Test-Path $ShortcutPath) {
    Remove-Item $ShortcutPath -Force
    Write-Host "[OK] Raccourci demarrage supprime." -ForegroundColor Green
}

Write-Host "Desinstallation terminee avec succes." -ForegroundColor Cyan
