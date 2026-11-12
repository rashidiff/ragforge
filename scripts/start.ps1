param([string]$PythonExecutable = "")
$ErrorActionPreference = "Stop"
$projectDirectory = Split-Path -Parent $PSScriptRoot
if (-not $PythonExecutable) {
    $PythonExecutable = Join-Path $projectDirectory ".venv\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $PythonExecutable)) {
    throw "Python environment not found. Follow the README setup or pass -PythonExecutable with an absolute Python path."
}
Push-Location (Join-Path $projectDirectory "backend")
try {
    & $PythonExecutable -m app
    if ($LASTEXITCODE -ne 0) { throw "Backend exited with code $LASTEXITCODE" }
} finally {
    Pop-Location
}
