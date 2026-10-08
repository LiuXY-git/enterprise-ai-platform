[CmdletBinding()]
param(
    [switch]$ApiOnly,
    [switch]$WithoutN8n,
    [ValidateSet('llm', 'dify', 'external-knowledge', 'feishu', 'wecom')]
    [string[]]$CheckComponents = @()
)

. (Join-Path $PSScriptRoot 'deployment-common.ps1')
if ($ApiOnly -and $WithoutN8n) { throw 'Choose ApiOnly or WithoutN8n, not both.' }
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
    $frontendId = Get-PlatformContainer $compose 'frontend'
    Assert-PlatformHealthy $frontendId 'frontend'
    $frontendUser = (Invoke-PlatformDocker @('inspect', '--format', '{{.Config.User}}', $frontendId) | Out-String).Trim()
    if ($frontendUser -ne 'nginx') { throw 'Frontend must run as the nginx user.' }
    Invoke-PlatformDocker @('exec', $frontendId, 'nginx', '-t') | Out-Host
    # Cross-container HTTP checks include the reverse proxy, not just static health.
    $frontendProbe = @'
import json, time, urllib.error, urllib.request
with urllib.request.urlopen('http://frontend:8080/', timeout=5) as response:
    assert 'KNOWLEDGE HUB' in response.read().decode('utf-8')
for path in ('app.js', 'styles.css'):
    with urllib.request.urlopen('http://frontend:8080/' + path, timeout=5) as response:
        assert response.read(), 'Missing frontend asset'
for attempt in range(6):
    try:
        with urllib.request.urlopen('http://frontend:8080/api/health', timeout=5) as response:
            assert json.load(response)['status'] == 'ok', 'Frontend API proxy failed'
        break
    except (urllib.error.URLError, TimeoutError):
        if attempt == 5:
            raise
        time.sleep(3)  # Allow Nginx DNS cache to refresh after API recreation.
print('Frontend page, assets and API reverse proxy verified.')
'@
    Invoke-PlatformDocker @('exec', $apiId, 'python', '-c', $frontendProbe) | Out-Host
}

if (-not $ApiOnly -and -not $WithoutN8n) {
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
