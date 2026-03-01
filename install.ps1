# ──────────────────────────────────────────────────────────────
# Skaro installer for Windows (PowerShell 5.1+)
#
# Usage:
#   irm https://raw.githubusercontent.com/skarodev/skaro/main/install.ps1 | iex
#
# What it does:
#   1. Finds Python 3.11+
#   2. Creates isolated venv at %USERPROFILE%\.skaro\venv
#   3. Installs (or upgrades) the 'skaro' package from PyPI
#   4. Creates 'skaro.cmd' shim in %USERPROFILE%\.skaro\bin and adds it to user PATH
#
# Uninstall:
#   Remove-Item -Recurse -Force "$env:USERPROFILE\.skaro\venv", "$env:USERPROFILE\.skaro\bin\skaro.cmd"
# ──────────────────────────────────────────────────────────────
$ErrorActionPreference = 'Stop'

# ── Config ──────────────────────────────────────
$SkaroHome = if ($env:SKARO_HOME) { $env:SKARO_HOME } else { Join-Path $env:USERPROFILE '.skaro' }
$VenvDir   = Join-Path $SkaroHome 'venv'
$BinDir    = Join-Path $SkaroHome 'bin'
$Package   = 'skaro'
$MinPythonMinor = 11

# ── Helpers ─────────────────────────────────────
function Write-Info  { param($M) Write-Host "▸ $M" -ForegroundColor Cyan }
function Write-Ok    { param($M) Write-Host "✓ $M" -ForegroundColor Green }
function Write-Warn  { param($M) Write-Host "⚠ $M" -ForegroundColor Yellow }
function Write-Fail  { param($M) Write-Host "✗ $M" -ForegroundColor Red; exit 1 }

# ── Find Python 3.11+ ──────────────────────────
function Find-Python {
    $candidates = @('python3.13','python3.12','python3.11','python3','python','py')
    foreach ($cmd in $candidates) {
        $exe = Get-Command $cmd -ErrorAction SilentlyContinue
        if (-not $exe) { continue }

        # Special handling for 'py' launcher — request 3.11+
        if ($cmd -eq 'py') {
            try {
                $ver = & py -3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
                if ($ver) {
                    $parts = $ver.Split('.')
                    if ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge $MinPythonMinor) {
                        return @{ Cmd = 'py'; Args = @('-3'); Version = $ver; Path = $exe.Source }
                    }
                }
            } catch { continue }
        }

        try {
            $ver = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if (-not $ver) { continue }
            $parts = $ver.Split('.')
            if ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge $MinPythonMinor) {
                return @{ Cmd = $cmd; Args = @(); Version = $ver; Path = $exe.Source }
            }
        } catch { continue }
    }
    return $null
}

# ── Python command wrapper (handles 'py -3' vs 'python3') ──
function Invoke-Python {
    param([hashtable]$Py, [string[]]$Arguments)
    $allArgs = $Py.Args + $Arguments
    & $Py.Cmd @allArgs
}

# ── Main ────────────────────────────────────────
function Main {
    Write-Host "`nSkaro Installer`n" -ForegroundColor White -NoNewline
    Write-Host "" # newline

    # 1. Find Python
    Write-Info "Looking for Python 3.$MinPythonMinor+..."
    $py = Find-Python
    if (-not $py) {
        Write-Fail "Python 3.$MinPythonMinor+ not found. Install from https://www.python.org/downloads/"
    }
    Write-Ok "Found: Python $($py.Version) ($($py.Path))"

    # 2. Create or reuse venv
    if (Test-Path (Join-Path $VenvDir 'Scripts')) {
        Write-Info "Existing venv found at $VenvDir — upgrading..."
    } else {
        Write-Info "Creating venv at $VenvDir..."
        New-Item -ItemType Directory -Path $SkaroHome -Force | Out-Null
        Invoke-Python -Py $py -Arguments @('-m','venv',$VenvDir)
        if ($LASTEXITCODE -ne 0) { Write-Fail "Failed to create venv." }
        Write-Ok "Venv created"
    }

    # 3. Install / upgrade
    $pip = Join-Path $VenvDir 'Scripts\pip.exe'
    if (-not (Test-Path $pip)) {
        Write-Fail "pip not found in venv at $pip"
    }

    Write-Info "Installing $Package (this may take a moment)..."

    # pip writes progress and warnings to stderr — temporarily allow that
    $ErrorActionPreference = 'Continue'
    & $pip install --upgrade pip 2>&1 | Out-Null
    & $pip install --upgrade $Package 2>&1
    $pipExit = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'

    if ($pipExit -ne 0) { Write-Fail "pip install failed." }

    $installedVersion = (& $pip show $Package 2>$null | Select-String '^Version:') -replace 'Version:\s*',''
    Write-Ok "Installed $Package $installedVersion"

    # 4. Create shim in BinDir
    New-Item -ItemType Directory -Path $BinDir -Force | Out-Null
    $skaroExe = Join-Path $VenvDir 'Scripts\skaro.exe'

    if (-not (Test-Path $skaroExe)) {
        Write-Fail "Binary not found at $skaroExe — package may have failed to install."
    }

    $shimPath = Join-Path $BinDir 'skaro.cmd'
    Set-Content -Path $shimPath -Value "@echo off`r`n`"$skaroExe`" %*" -Encoding ASCII
    Write-Ok "Created shim: $shimPath"

    # 5. Ensure BinDir is in user PATH
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    if ($userPath -notlike "*$BinDir*") {
        $newPath = "$BinDir;$userPath"
        [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
        # Also update current session
        $env:Path = "$BinDir;$env:Path"
        Write-Ok "Added $BinDir to user PATH"
        Write-Warn "Restart your terminal for PATH changes to take effect in new sessions."
    } else {
        Write-Ok "$BinDir already in PATH"
    }

    # 6. Done
    Write-Host ""
    Write-Host "Done! " -ForegroundColor Green -NoNewline
    Write-Host "Run " -NoNewline
    Write-Host "skaro" -ForegroundColor Cyan -NoNewline
    Write-Host " to get started."
    Write-Host "  cd my-project; skaro init; skaro ui" -ForegroundColor Cyan
    Write-Host ""
}

Main
