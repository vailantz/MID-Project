param([switch]$UseExisting)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (!(Test-Path '.venv/Scripts/python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE) { throw 'Python 3.10 or newer is required.' }
}
$python = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
function Run-Python {
    $nativePreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $python @args
        $commandExit = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $nativePreference
    }
    if ($commandExit) { throw 'Python command failed; see the error above.' }
}
Run-Python -m pip install -r requirements.txt
if ($UseExisting) {
    Run-Python scripts/install_tools.py --check-running
} else {
    Run-Python scripts/install_tools.py
    & powershell -NoProfile -ExecutionPolicy Bypass -File database/start.ps1 -SkipQwen
    if ($LASTEXITCODE) { throw 'Database startup failed.' }
}
Run-Python scripts/test_rules.py
Run-Python scripts/data.py
Run-Python scripts/ingest.py --reset
if (Test-Path 'data/embeddings/manifest.json') {
    Run-Python scripts/embeddings.py import
}
Run-Python scripts/test_databases.py
Write-Host 'Ready. See README.md for queries and optional semantic indexing.'
