$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$basexState = Join-Path $projectRoot '.runtime\basex_p1'
$configuration = Join-Path $basexState '.basex'
if (-not (Test-Path -LiteralPath $configuration)) {
    throw 'Preparar primeiro: python -X utf8 scripts/check_basex_p1.py'
}
$dbPathLine = Get-Content -LiteralPath $configuration | Where-Object { $_ -match '^DBPATH\s*=' }
if (@($dbPathLine).Count -ne 1) {
    throw 'Configuracao BaseX P1 invalida: DBPATH ausente ou repetido.'
}
$configuredPath = [System.IO.Path]::GetFullPath(($dbPathLine -split '=', 2)[1].Trim())
$expectedPath = [System.IO.Path]::GetFullPath((Join-Path $basexState 'data'))
if ($configuredPath -ne $expectedPath) {
    throw 'DBPATH fora da pasta reservada para BaseX P1. Nenhuma base foi aberta.'
}
& java "-Dorg.basex.path=$basexState" -cp (Join-Path $projectRoot 'tools\BaseX124.jar') org.basex.BaseX @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
