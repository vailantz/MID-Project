# Exemplo: .\scripts\basex.ps1 -i .\data\cultural_catalogue.xml -Q .\xml_basex\02_counts.xq
# Os argumentos sao passados ao BaseX; o estado fica apenas nesta pasta de trabalho.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$basexState = Join-Path $projectRoot '.runtime\basex'
New-Item -ItemType Directory -Force -Path $basexState | Out-Null
& java "-Dorg.basex.path=$basexState" -cp (Join-Path $projectRoot 'tools\BaseX124.jar') org.basex.BaseX @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
