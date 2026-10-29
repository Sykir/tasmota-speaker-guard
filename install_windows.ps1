# Tasmota Speaker Guard - Windows Autostart Installer
# Configures a Scheduled Task running the script silently in the background at logon.

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonwExe = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source

if (-not $PythonwExe) {
    if (Test-Path "C:\Python311\pythonw.exe") {
        $PythonwExe = "C:\Python311\pythonw.exe"
    } else {
        Write-Error "pythonw.exe not found. Please verify your Python installation and PATH."
        exit 1
    }
}

$PywFile = Join-Path $ScriptDir "speaker_guard.pyw"
$TaskName = "TasmotaSpeakerGuard"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "     Installing Tasmota Speaker Guard for Windows         " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Check and clean up existing task
$ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($ExistingTask) {
    Write-Host "Updating existing Scheduled Task..." -ForegroundColor Yellow
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# 2. Register Scheduled Task
$Action = New-ScheduledTaskAction -Execute $PythonwExe -Argument "`"$PywFile`"" -WorkingDirectory $ScriptDir
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0 -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

try {
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Tasmota Speaker Guard" | Out-Null
    Write-Host "[OK] Scheduled Task '$TaskName' registered successfully!" -ForegroundColor Green
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "[OK] Background service started." -ForegroundColor Green
} catch {
    Write-Warning "Failed to register Scheduled Task ($($_.Exception.Message)). Falling back to shell:startup..."
    $WshShell = New-Object -ComObject WScript.Shell
    $StartupDir = [Environment]::GetFolderPath("Startup")
    $ShortcutPath = Join-Path $StartupDir "TasmotaSpeakerGuard.lnk"
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $PythonwExe
    $Shortcut.Arguments = "`"$PywFile`""
    $Shortcut.WorkingDirectory = $ScriptDir
    $Shortcut.Save()
    Write-Host "[OK] Shortcut created in shell:startup folder" -ForegroundColor Green
    Start-Process $PythonwExe -ArgumentList "`"$PywFile`"" -WorkingDirectory $ScriptDir
}
