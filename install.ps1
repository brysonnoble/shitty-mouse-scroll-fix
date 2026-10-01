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

# Task Manager's Startup apps list names an entry after its target exe's file
# description, which for pythonw.exe is just "Python". Build a tiny launcher exe
# with our own name that hands its arguments to pythonw and exits.
$launcher = Join-Path $PSScriptRoot 'shitty-mouse-scroll-fix.exe'
$launcherSource = @"
using System.Diagnostics;
using System.Reflection;
[assembly: AssemblyTitle("Shitty Mouse Scroll Fix")]
[assembly: AssemblyProduct("Shitty Mouse Scroll Fix")]
public static class Launcher {
    public static void Main() {
        // Pass our raw command line, minus our own path, through to pythonw.
        string cmd = System.Environment.CommandLine.TrimStart();
        int end = cmd.StartsWith("\"") ? cmd.IndexOf('"', 1) + 1 : cmd.IndexOf(' ');
        string rest = end <= 0 || end >= cmd.Length ? "" : cmd.Substring(end).TrimStart();
        ProcessStartInfo psi = new ProcessStartInfo(@"$pythonw", rest);
        psi.UseShellExecute = false;
        psi.WorkingDirectory = @"$PSScriptRoot";
        Process.Start(psi);
    }
}
"@
if (Test-Path $launcher) { Remove-Item $launcher -Force }
Add-Type -TypeDefinition $launcherSource -OutputAssembly $launcher -OutputType WindowsApplication

$startup = [Environment]::GetFolderPath('Startup')
$lnkPath = Join-Path $startup 'shitty-mouse-scroll-fix.lnk'
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($lnkPath)
$lnk.TargetPath = $launcher
$lnk.Arguments = $argString
$lnk.WorkingDirectory = $PSScriptRoot
$lnk.Description = 'Blocks spurious scroll-wheel reversals'
$lnk.Save()
Write-Host "Startup shortcut created: $lnkPath"

# Restart so new arguments take effect.
& (Join-Path $PSScriptRoot 'uninstall.ps1') -StopOnly
Start-Process -FilePath $pythonw -ArgumentList $argString -WorkingDirectory $PSScriptRoot
Write-Host 'scroll fix is now running in the background.'
