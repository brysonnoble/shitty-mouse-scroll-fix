# Installs shitty-mouse-scroll-fix to run at logon (Startup folder shortcut)
# and starts it immediately. Any arguments are passed through to scroll_fix.py,
# e.g.  .\install.ps1 --threshold 4 --timeout 500

$ErrorActionPreference = 'Stop'

$script = Join-Path $PSScriptRoot 'scroll_fix.py'
$python = & python -c "import sys; print(sys.executable)"
if (-not $python) { throw 'Python not found on PATH.' }
$pythonw = Join-Path (Split-Path $python) 'pythonw.exe'
if (-not (Test-Path $pythonw)) { throw "pythonw.exe not found next to $python" }

$argString = (@("`"$script`"") + $args) -join ' '

$startup = [Environment]::GetFolderPath('Startup')
$lnkPath = Join-Path $startup 'shitty-mouse-scroll-fix.lnk'
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($lnkPath)
$lnk.TargetPath = $pythonw
$lnk.Arguments = $argString
$lnk.WorkingDirectory = $PSScriptRoot
$lnk.Description = 'Blocks spurious scroll-wheel reversals'
$lnk.Save()
Write-Host "Startup shortcut created: $lnkPath"

# Restart so new arguments take effect.
& (Join-Path $PSScriptRoot 'uninstall.ps1') -StopOnly
Start-Process -FilePath $pythonw -ArgumentList $argString -WorkingDirectory $PSScriptRoot
Write-Host 'scroll fix is now running in the background.'
