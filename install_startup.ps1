# Script d'installation du demarrage automatique pour Tasmota Speaker Guard
# Ce script configure une tache planifiee Windows qui demarre automatiquement le script
# en arriere-plan (sans fenetre console) lors de l'ouverture de votre session.

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonwExe = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source

if (-not $PythonwExe) {
    # Tente de trouver dans C:\Python311 ou AppData
    if (Test-Path "C:\Python311\pythonw.exe") {
        $PythonwExe = "C:\Python311\pythonw.exe"
    } else {
        Write-Error "Impossible de trouver pythonw.exe. Verifiez que Python est bien dans votre PATH."
        exit 1
    }
}

$PywFile = Join-Path $ScriptDir "speaker_guard.pyw"
$TaskName = "TasmotaSpeakerGuard"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   Installation de Tasmota Speaker Guard au demarrage     " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Pythonw : $PythonwExe"
Write-Host "Script  : $PywFile"
Write-Host "Dossier : $ScriptDir"
Write-Host ""

# 1. Verification de la tache existante
$ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($ExistingTask) {
    Write-Host "Suppression de l'ancienne tache planifiee..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# 2. Creation de la tache planifiee Windows
$Action = New-ScheduledTaskAction -Execute $PythonwExe -Argument "`"$PywFile`"" -WorkingDirectory $ScriptDir
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0 -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

try {
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Gestionnaire automatique d'alimentation des enceintes via prise Tasmota" | Out-Null
    Write-Host "[OK] Tache planifiee '$TaskName' enregistree avec succes !" -ForegroundColor Green
    
    # 3. Lancement immediat de la tache
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "[OK] Le service a ete demarre en arriere-plan." -ForegroundColor Green
} catch {
    Write-Warning "Echec de creation de la tache planifiee ($($_.Exception.Message))."
    Write-Host "Creation d'un raccourci dans le dossier de demarrage (shell:startup) en secours..." -ForegroundColor Yellow
    
    $WshShell = New-Object -ComObject WScript.Shell
    $StartupDir = [Environment]::GetFolderPath("Startup")
    $ShortcutPath = Join-Path $StartupDir "TasmotaSpeakerGuard.lnk"
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $PythonwExe
    $Shortcut.Arguments = "`"$PywFile`""
    $Shortcut.WorkingDirectory = $ScriptDir
    $Shortcut.Description = "Tasmota Speaker Guard"
    $Shortcut.Save()
    
    Write-Host "[OK] Raccourci cree dans : $ShortcutPath" -ForegroundColor Green
    Start-Process $PythonwExe -ArgumentList "`"$PywFile`"" -WorkingDirectory $ScriptDir
}

Write-Host ""
Write-Host "Pour verifier l'etat du service, consultez le fichier :" -ForegroundColor Cyan
Write-Host (Join-Path $ScriptDir "speaker_guard.log") -ForegroundColor White
Write-Host ""
