# Bootstrap the OpenAntenna Studio development environment on Windows.
#
#   powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
#
# Creates .venv, installs the pinned analysis dependencies and, when
# OPENEMS_ROOT points at an openEMS installation, installs the matching
# solver wheels.  The core package and the test suite need none of this.

[CmdletBinding()]
param(
    [string]$VenvPath = ".venv",
    [string]$OpenEmsRoot = $env:OPENEMS_ROOT,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Write-Step($message) { Write-Host "==> $message" -ForegroundColor Cyan }

# --- 1. pick an interpreter -------------------------------------------------
$launcher = Get-Command py -ErrorAction SilentlyContinue
if ($launcher) {
    $python = @("py", "-3")
} else {
    $python = @("python")
}
Write-Step "using interpreter: $($python -join ' ')"
& $python[0] $python[1..($python.Count - 1)] --version

# --- 2. virtual environment -------------------------------------------------
if (-not (Test-Path (Join-Path $VenvPath "Scripts\python.exe"))) {
    Write-Step "creating virtual environment in $VenvPath"
    & $python[0] $python[1..($python.Count - 1)] -m venv $VenvPath
} else {
    Write-Step "virtual environment already exists in $VenvPath"
}
$venvPython = Join-Path $repoRoot (Join-Path $VenvPath "Scripts\python.exe")

# --- 3. analysis dependencies (optional) ------------------------------------
if (Test-Path "requirements-lock.txt") {
    Write-Step "installing pinned analysis dependencies"
    & $venvPython -m pip install --upgrade pip --quiet
    & $venvPython -m pip install --quiet -r requirements-lock.txt
    & $venvPython -m pip list | Select-String -Pattern "numpy|scipy|matplotlib|pytest|scikit-rf|h5py"
}

# --- 4. solver bindings (optional, needs the openEMS package) ---------------
if ($OpenEmsRoot -and (Test-Path $OpenEmsRoot)) {
    Write-Step "looking for openEMS python wheels in $OpenEmsRoot\python"
    $tag = & $venvPython -c "import sys; print('cp%d%d' % sys.version_info[:2])"
    $wheels = Get-ChildItem -Path (Join-Path $OpenEmsRoot "python") -Filter "*$tag*.whl" -ErrorAction SilentlyContinue
    if ($wheels) {
        foreach ($wheel in $wheels) {
            Write-Step "installing $($wheel.Name)"
            & $venvPython -m pip install --quiet $wheel.FullName
        }
        Write-Host ""
        Write-Host "Set this for every shell that runs simulations:" -ForegroundColor Yellow
        Write-Host "  `$env:OPENEMS_ROOT = `"$OpenEmsRoot`""
    } else {
        Write-Host "No wheels matching $tag found. Download the openEMS Windows package from" -ForegroundColor Yellow
        Write-Host "https://github.com/thliebig/openEMS-Project/releases and unzip it, then re-run." -ForegroundColor Yellow
    }
} else {
    Write-Host ""
    Write-Host "OPENEMS_ROOT is not set: skipping the solver bindings." -ForegroundColor Yellow
    Write-Host "Simulations will not run until it points at an openEMS package folder." -ForegroundColor Yellow
}

# --- 5. tests ---------------------------------------------------------------
if (-not $SkipTests) {
    Write-Step "running the test suite"
    Push-Location $repoRoot
    & $venvPython -m unittest discover -s tests
    Pop-Location
}

Write-Host ""
Write-Step "done"
