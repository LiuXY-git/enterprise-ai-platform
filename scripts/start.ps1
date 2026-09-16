[CmdletBinding()]
param(
    [switch]$ApiOnly,
    [ValidateRange(30, 600)][int]$WaitTimeoutSeconds = 120,
    [ValidateSet('llm', 'dify', 'external-knowledge', 'feishu', 'wecom')]
    [string[]]$CheckComponents = @()
)

. (Join-Path $PSScriptRoot 'deployment-common.ps1')
$projectRoot = Split-Path -Parent $PSScriptRoot
$compose = @(Get-PlatformComposeArguments $projectRoot)

Test-PlatformDocker
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot '.env') -PathType Leaf)) {
    throw 'Project .env is missing. Copy .env.example and configure it locally first.'
}
Invoke-PlatformDocker ($compose + @('config', '--quiet')) | Out-Null

# Build before replacing a healthy container. No down, volume deletion or pruning.
Write-Host 'Building API image...'
Invoke-PlatformDocker ($compose + @('build', 'api')) | Out-Host
$up = $compose + @('up', '-d', '--no-build', '--wait',
    '--wait-timeout', [string]$WaitTimeoutSeconds)
if ($ApiOnly) {
    $up += @('--no-deps', 'api')
} else {
    $up += @('api', 'n8n')
}
Invoke-PlatformDocker $up | Out-Host

$verify = @{ CheckComponents = $CheckComponents }
if ($ApiOnly) { $verify.ApiOnly = $true }
& (Join-Path $PSScriptRoot 'check-deployment.ps1') @verify
Write-Host 'Deployment completed and verified.' -ForegroundColor Green
