# Alias for uninstall_windows.ps1
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $ScriptDir "uninstall_windows.ps1")
