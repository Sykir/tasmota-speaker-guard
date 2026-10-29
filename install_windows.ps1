# Script d'installation du demarrage automatique pour Tasmota Speaker Guard sous Windows
# Configure une tache planifiee qui demarre le script en arriere-plan sans invite de commande.

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonwExe = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source

if (-not $PythonwExe) {
    if (Test-Path "C:\Python311\pythonw.exe") {
        $PythonwExe = "C:\Python311\pythonw.exe"
    } else {
        Write-Error "pythonw.exe introuvable. Verifiez votre installation de Python."
        exit 1
    }
}

$PywFile = Join-Path $ScriptDir "speaker_guard.pyw"
$TaskName = "TasmotaSpeakerGuard"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   Installation de Tasmota Speaker Guard sous Windows     " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Verification et nettoyage ancienne tache
$ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($ExistingTask) {
    Write-Host "Mise a jour de la tache existante..." -ForegroundColor Yellow
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# 2. Creation de la tache planifiee
$Action = New-ScheduledTaskAction -Execute $PythonwExe -Argument "`"$PywFile`"" -WorkingDirectory $ScriptDir
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0 -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

try {
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Tasmota Speaker Guard" | Out-Null
    Write-Host "[OK] Tache planifiee '$TaskName' enregistree !" -ForegroundColor Green
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "[OK] Service demarre en arriere-plan." -ForegroundColor Green
} catch {
    Write-Warning "Echec de creation de la tache ($($_.Exception.Message)). Repli sur shell:startup..."
    $WshShell = New-Object -ComObject WScript.Shell
    $StartupDir = [Environment]::GetFolderPath("Startup")
    $ShortcutPath = Join-Path $StartupDir "TasmotaSpeakerGuard.lnk"
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $PythonwExe
    $Shortcut.Arguments = "`"$PywFile`""
    $Shortcut.WorkingDirectory = $ScriptDir
    $Shortcut.Save()
    Write-Host "[OK] Raccourci place dans shell:startup" -ForegroundColor Green
    Start-Process $PythonwExe -ArgumentList "`"$PywFile`"" -WorkingDirectory $ScriptDir
}
