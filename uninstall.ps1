# Stops shitty-mouse-scroll-fix and removes it from startup.
# -StopOnly: just stop the running instance, keep the startup shortcut.
param([switch]$StopOnly)

$procs = Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe' OR Name = 'python.exe'" |
    Where-Object { $_.CommandLine -like '*scroll_fix.py*' }
foreach ($p in $procs) {
    Stop-Process -Id $p.ProcessId -Force
    Write-Host "Stopped scroll fix (PID $($p.ProcessId))."
}

if (-not $StopOnly) {
    $lnkPath = Join-Path ([Environment]::GetFolderPath('Startup')) 'shitty-mouse-scroll-fix.lnk'
    if (Test-Path $lnkPath) {
        Remove-Item $lnkPath
        Write-Host "Removed startup shortcut."
    }
    $launcher = Join-Path $PSScriptRoot 'shitty-mouse-scroll-fix.exe'
    if (Test-Path $launcher) { Remove-Item $launcher -Force }
}
