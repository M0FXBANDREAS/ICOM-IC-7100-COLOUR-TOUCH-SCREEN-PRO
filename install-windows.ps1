$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
Start-Transcript -Path (Join-Path $PSScriptRoot 'install-log.txt') -Force | Out-Null
Write-Host 'HamTech M0FXB Modification - Windows 11 setup' -ForegroundColor Cyan
function Find-Python {
    foreach ($version in @('313','312','314')) {
        foreach ($base in @("$env:LOCALAPPDATA\Programs\Python", "$env:ProgramFiles")) {
            $candidate = Join-Path $base "Python$version\python.exe"
            if (Test-Path $candidate) { return $candidate }
        }
    }
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        foreach ($version in @('3.13','3.12','3.14')) {
            try {
                $output = & $py.Source "-$version" -c 'import sys; print(sys.executable)' 2>$null
                if ($LASTEXITCODE -eq 0 -and $output) {
                    $candidate = ($output | Select-Object -Last 1).Trim()
                    if (Test-Path $candidate) { return $candidate }
                }
            } catch { }
        }
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
    Stop-Transcript | Out-Null
    exit 1
}
Stop-Transcript | Out-Null

