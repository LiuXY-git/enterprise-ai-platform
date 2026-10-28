[CmdletBinding()]
param(
    [ValidateSet('start','check','stop','logs')][string]$Action = 'check',
    [ValidatePattern('^[a-z0-9][a-z0-9_-]+$')][string]$ProjectName = 'enterprise-console',
    [ValidateSet('api','worker','frontend')][string]$Service = 'worker',
    [switch]$SkipBuild
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
. (Join-Path $projectRoot 'scripts/deployment-common.ps1')
Test-PlatformDocker
$compose = @('compose','--ansi','never','--progress','plain','--project-directory',$projectRoot,
    '-p',$ProjectName,'-f',(Join-Path $projectRoot 'compose.console.yaml'))
if ($Action -eq 'stop') {
    Invoke-PlatformDocker ($compose + @('down'))
    Write-Host 'Console stopped. Persistent data retained.'
    return
}
if ($Action -eq 'logs') {
    Invoke-PlatformDocker ($compose + @('logs','--no-color','--tail','100',$Service))
    return
}
if ($Action -eq 'start') {
    if (-not $SkipBuild) { Invoke-PlatformDocker ($compose + @('build')) }
    Invoke-PlatformDocker ($compose + @('up','-d','--wait','--wait-timeout','180'))
}
foreach ($name in @('api','worker','frontend')) {
    $container = Get-PlatformContainer $compose $name
    Assert-PlatformHealthy $container $name
}
$api = Get-PlatformContainer $compose 'api'
$worker = Get-PlatformContainer $compose 'worker'
$apiMount = (Invoke-PlatformDocker @('inspect','--format','{{json .Mounts}}',$api) | ConvertFrom-Json) |
    Where-Object { $_.Destination -eq '/app/console-data' }
$workerMount = (Invoke-PlatformDocker @('inspect','--format','{{json .Mounts}}',$worker) | ConvertFrom-Json) |
    Where-Object { $_.Destination -eq '/app/console-data' }
function Convert-ConsoleHostPath([string]$Value) {
    $normalized = $Value.Replace('\','/')
    if ($normalized -match '^/(?:run/desktop/mnt/host|host_mnt)/([a-zA-Z])/(.*)$') {
        $normalized = $Matches[1] + ':/' + $Matches[2]
    }
    return $normalized.TrimEnd('/').ToLowerInvariant()
}
if (-not $apiMount -or -not $workerMount -or -not $apiMount.RW -or -not $workerMount.RW -or
    (Convert-ConsoleHostPath $apiMount.Source) -ne (Convert-ConsoleHostPath $workerMount.Source)) { throw 'API and worker must share one writable queue directory.' }
# Execute the health command as the image's unprivileged user.
$evaluationMount = (Invoke-PlatformDocker @('inspect','--format','{{json .Mounts}}',$worker) | ConvertFrom-Json) |
    Where-Object { $_.Destination -eq '/app/evaluation-data' }
if (-not $evaluationMount -or $evaluationMount.Type -ne 'volume' -or -not $evaluationMount.RW) {
    throw 'Worker must mount a writable persistent evaluation volume.'
}
Invoke-PlatformDocker ($compose + @('exec','-T','worker','python','-B','-c',
    'import os; assert os.geteuid() != 0; assert os.access("/app/evaluation-data", os.W_OK)'))
Invoke-PlatformDocker ($compose + @('exec','-T','worker','python','-B','-m','backend.app.console.worker','--healthcheck'))
$pages = @('','workflows.html','sales.html','evaluations.html')
# Docker DNS can retain the old API address briefly after recreation. Retry only GETs.
function Read-ConsoleEndpoint([string]$Path, [switch]$Json) {
    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    do {
        try {
            $url = "http://127.0.0.1:18080/$Path"
            if ($Json) { return Invoke-RestMethod $url -TimeoutSec 5 }
            return Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 5
        } catch {
            if ([DateTime]::UtcNow -ge $deadline) { throw "Console GET check failed: $Path; inspect API/frontend logs." }
            Start-Sleep -Milliseconds 500
        }
    } while ($true)
}
foreach ($page in $pages) {
    $response = Read-ConsoleEndpoint $page
    if ($response.StatusCode -ne 200) { throw "Page unavailable: $page" }
}
$capabilities = Read-ConsoleEndpoint 'api/console/capabilities' -Json
$heartbeat = Read-ConsoleEndpoint 'api/console/worker' -Json
if ($heartbeat.status -ne 'healthy' -or -not $capabilities.evaluation_runs_available -or
    -not $capabilities.workflow_execution_available) { throw 'Console capability or worker check failed.' }
Invoke-PlatformDocker ($compose + @('ps'))
Write-Host 'Console ready: http://127.0.0.1:18080/ ; four pages, shared storage and worker verified.'
Write-Host 'This check does not execute models, approve proposals or verify live n8n dependencies.'
