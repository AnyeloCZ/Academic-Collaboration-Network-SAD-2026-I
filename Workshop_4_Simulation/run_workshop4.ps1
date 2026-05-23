$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$bundledPython = "C:\Users\santi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (Test-Path -LiteralPath $bundledPython) {
    & $bundledPython ".\src\run_simulations.py"
} else {
    Write-Host "Bundled Python was not found."
    Write-Host "Trying system Python instead..."
    python ".\src\run_simulations.py"
}

Write-Host ""
Write-Host "Finished. Outputs are in docs, figures, and results."
