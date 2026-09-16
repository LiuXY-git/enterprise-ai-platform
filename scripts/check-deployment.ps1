[CmdletBinding()]
param(
    [switch]$ApiOnly,
    [ValidateSet('llm', 'dify', 'external-knowledge', 'feishu', 'wecom')]
    [string[]]$CheckComponents = @()
)

. (Join-Path $PSScriptRoot 'deployment-common.ps1')
$projectRoot = Split-Path -Parent $PSScriptRoot
$compose = @(Get-PlatformComposeArguments $projectRoot)
Test-PlatformDocker
Invoke-PlatformDocker ($compose + @('config', '--quiet')) | Out-Null
$apiId = Get-PlatformContainer $compose 'api'
Assert-PlatformHealthy $apiId 'api'
$apiUser = (Invoke-PlatformDocker @('inspect', '--format', '{{.Config.User}}', $apiId) | Out-String).Trim()
if ($apiUser -ne 'app') { throw 'API must run as the app user.' }
$mounts = (Invoke-PlatformDocker @('inspect', '--format', '{{json .Mounts}}', $apiId) | Out-String) | ConvertFrom-Json
Assert-PlatformBind $mounts '/app/data' (Join-Path $projectRoot 'data')
Assert-PlatformBind $mounts '/app/logs' (Join-Path $projectRoot 'logs')
Assert-PlatformBind $mounts '/home/app/.cache/chroma' (Join-Path $projectRoot 'data/chroma-cache')

# Check this container, not a potentially unrelated process on the host port.
$probe = @'
import json, sqlite3, urllib.request
from backend.app.database import DATABASE_PATH
from backend.app.logging_config import LOG_DIRECTORY
with urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5) as response:
    assert json.load(response)['status'] == 'ok', 'API health response failed'
with urllib.request.urlopen('http://127.0.0.1:8000/openapi.json', timeout=5) as response:
    paths = json.load(response)['paths']
    assert '/workflow-runs/start' in paths and '/dify/workflow' in paths
assert str(DATABASE_PATH) == '/app/data/enterprise_ai.db'
assert str(LOG_DIRECTORY) == '/app/logs'
connection = sqlite3.connect(DATABASE_PATH.as_uri() + '?mode=ro', uri=True)
try:
    assert connection.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
finally:
    connection.close()
assert (LOG_DIRECTORY / 'app.log').is_file()
assert (LOG_DIRECTORY / 'workflow-events.jsonl').is_file()
print('API health, OpenAPI, SQLite integrity and log paths verified.')
'@
Invoke-PlatformDocker @('exec', $apiId, 'python', '-c', $probe) | Out-Host

foreach ($component in $CheckComponents) {
    Invoke-PlatformDocker @('exec', $apiId, 'python', '-m',
        'backend.app.check_config', '--component', $component) | Out-Host
}

if (-not $ApiOnly) {
    $n8nId = Get-PlatformContainer $compose 'n8n'
    Assert-PlatformHealthy $n8nId 'n8n'
    $n8nMounts = (Invoke-PlatformDocker @('inspect', '--format', '{{json .Mounts}}', $n8nId) | Out-String) | ConvertFrom-Json
    $volume = @($n8nMounts | Where-Object { $_.Destination -eq '/home/node/.n8n' })
    if ($volume.Count -ne 1 -or $volume[0].Type -ne 'volume' -or -not $volume[0].RW) {
        throw 'n8n persistent volume is missing.'
    }
    Write-Host 'n8n is healthy and its persistent volume is mounted.'
}
Invoke-PlatformDocker ($compose + @('ps')) | Out-Host
Write-Host 'Deployment checks passed. Model/network credentials were not tested.' -ForegroundColor Green
