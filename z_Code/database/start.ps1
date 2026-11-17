param([int]$WaitSeconds = 120)
$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtime = Join-Path $project '.runtime'
$state = Join-Path $runtime 'state'
New-Item -ItemType Directory -Force -Path $state | Out-Null
$mongo = Get-ChildItem -LiteralPath (Join-Path $runtime 'mongodb') -Filter mongod.exe -Recurse | Select-Object -First 1
$elastic = Get-ChildItem -LiteralPath (Join-Path $runtime 'elasticsearch') -Filter elasticsearch.bat -Recurse | Select-Object -First 1
if (!$mongo -or !$elastic) { throw 'Run python scripts/install_tools.py first.' }

if (!(Test-NetConnection 127.0.0.1 -Port 27017 -InformationLevel Quiet -WarningAction SilentlyContinue)) {
    $db = Join-Path $state 'mongo'
    New-Item -ItemType Directory -Force -Path $db | Out-Null
    $log = Join-Path $state 'mongo.log'
    $process = Start-Process -FilePath $mongo.FullName -ArgumentList @('--dbpath', "`"$db`"", '--logpath', "`"$log`"", '--bind_ip', '127.0.0.1', '--port', '27017', '--wiredTigerCacheSizeGB', '0.5') -WindowStyle Hidden -PassThru
    $process.Id | Set-Content (Join-Path $state 'mongo.pid')
}

if (!(Test-NetConnection 127.0.0.1 -Port 9200 -InformationLevel Quiet -WarningAction SilentlyContinue)) {
    $elasticHome = $elastic.Directory.Parent.FullName
    @'
cluster.name: dmi-79189
node.name: local-1
network.host: 127.0.0.1
http.port: 9200
transport.port: 9300
discovery.type: single-node
xpack.security.enabled: false
xpack.security.enrollment.enabled: false
xpack.ml.enabled: false
ingest.geoip.downloader.enabled: false
'@ | Set-Content -Encoding ascii (Join-Path $elasticHome 'config/elasticsearch.yml')
    $env:ES_JAVA_OPTS = '-Xms1g -Xmx1g'
    $process = Start-Process -FilePath $elastic.FullName -WorkingDirectory $elasticHome -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $state 'elastic.out.log') -RedirectStandardError (Join-Path $state 'elastic.err.log')
    $process.Id | Set-Content (Join-Path $state 'elastic.pid')
}

$deadline = (Get-Date).AddSeconds($WaitSeconds)
do {
    try {
        $health = Invoke-RestMethod 'http://127.0.0.1:9200/_cluster/health' -TimeoutSec 2
        if ($health.cluster_name -ne 'dmi-79189') { throw 'Port 9200 belongs to another Elasticsearch cluster.' }
        if ($health.status -in @('green', 'yellow')) {
            Write-Host 'MongoDB: mongodb://127.0.0.1:27017'
            Write-Host 'Elasticsearch: http://127.0.0.1:9200'
            exit 0
        }
    } catch { Start-Sleep -Seconds 2 }
} while ((Get-Date) -lt $deadline)
throw "Sources did not start. Check $state for logs."

