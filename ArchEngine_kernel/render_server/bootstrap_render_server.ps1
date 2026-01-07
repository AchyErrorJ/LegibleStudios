param(
    [string]$PythonExe = "python",
    [string]$VenvPath = (Join-Path $PSScriptRoot "..\\.venv-sd")
)

$ErrorActionPreference = "Stop"

$venvFull = Resolve-Path -LiteralPath $VenvPath -ErrorAction SilentlyContinue
if (-not $venvFull) {
    $venvFull = [System.IO.Path]::GetFullPath($VenvPath, $PSScriptRoot)
}

$requirements = Join-Path $PSScriptRoot "requirements.txt"
if (-not (Test-Path -LiteralPath $requirements)) {
    throw "Missing requirements.txt at $requirements"
}

Write-Host "Creating venv at $venvFull"
& $PythonExe -m venv $venvFull

$venvPython = Join-Path $venvFull "Scripts\\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Venv python not found at $venvPython"
}

Write-Host "Installing dependencies from $requirements"
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r $requirements

Write-Host "Done. Venv ready: $venvPython"
