$ErrorActionPreference = 'Stop'
$runtime = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../.runtime'))
# Stop only database processes launched from this package.
Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and $_.CommandLine.Contains($runtime) -and
    ($_.Name -eq 'mongod.exe' -or $_.Name -eq 'java.exe')
} | ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
