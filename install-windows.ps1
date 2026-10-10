$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
Write-Host 'HamTech M0FXB Modification - Windows 11 setup' -ForegroundColor Cyan
function Find-Python {
    $paths = @("$env:LOCALAPPDATA\Programs\Python\Python313\python.exe", "$env:ProgramFiles\Python313\python.exe")
    foreach ($path in $paths) { if (Test-Path $path) { return $path } }
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        $output = & $py.Source -3.13 -c 'import sys; print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0 -and $output) { return ($output | Select-Object -Last 1) }
    }
    return $null
}
try {
    $pythonExe = Find-Python
    if (-not $pythonExe) {
        if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
            Start-Process 'https://www.python.org/downloads/windows/'
            throw 'Install Python 3.13 (64-bit, including tkinter) from python.org, then run this setup again. WinGet is unavailable.'
        }
        Write-Host 'Installing Python 3.13 with Windows Package Manager...'
        & winget.exe install --exact --id Python.Python.3.13 --source winget --accept-source-agreements --accept-package-agreements
        if ($LASTEXITCODE -ne 0) { throw 'Python installation did not complete. Install Python 3.13 from python.org and retry.' }
        $pythonExe = Find-Python
        if (-not $pythonExe) { throw 'Python not found yet. Close this window and run setup again.' }
    }
    & $pythonExe -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
    & '.\.venv\Scripts\python.exe' -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'Could not update pip. Check your internet connection.' }
    & '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Read the pip output above.' }
    $shell = New-Object -ComObject WScript.Shell
    $desktop = [Environment]::GetFolderPath('Desktop')
    $shortcut = $shell.CreateShortcut((Join-Path $desktop 'HamTech IC-7100 Panel.lnk'))
    $shortcut.TargetPath = Join-Path $PSScriptRoot 'START-PANEL.cmd'
    $shortcut.WorkingDirectory = $PSScriptRoot
    $shortcut.Description = 'HamTech M0FXB Modification - IC-7100'
    $shortcut.Save()
    Write-Host 'Ready. Install the Icom USB driver if needed, then open START-PANEL.cmd.' -ForegroundColor Green
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
