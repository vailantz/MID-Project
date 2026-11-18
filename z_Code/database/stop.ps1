$ErrorActionPreference = 'Stop'
$runtime = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../.runtime'))
$encoderScript = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../scripts/query_encoder.py'))
# Stop only service processes launched from this package.
Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and (
        ($_.CommandLine.Contains($runtime) -and ($_.Name -eq 'mongod.exe' -or $_.Name -eq 'java.exe')) -or
        ($_.Name -eq 'python.exe' -and $_.CommandLine.Contains($encoderScript) -and $_.CommandLine.Contains('--serve'))
    )
} | ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
