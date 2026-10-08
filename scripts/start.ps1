[CmdletBinding()]
param(
    [string]$EnvFile = '.env',
    [switch]$ApiOnly,
    [switch]$WithoutN8n,
    [ValidateRange(30, 600)][int]$WaitTimeoutSeconds = 120,
    [ValidateSet('llm', 'dify', 'external-knowledge', 'feishu', 'wecom')]
    [string[]]$CheckComponents = @()
)

. (Join-Path $PSScriptRoot 'deployment-common.ps1')
if ($ApiOnly -and $WithoutN8n) { throw 'Choose ApiOnly or WithoutN8n, not both.' }
$projectRoot = Split-Path -Parent $PSScriptRoot
$compose = @(Get-PlatformComposeArguments $projectRoot $EnvFile)

Test-PlatformDocker
Invoke-PlatformDocker ($compose + @('config', '--quiet')) | Out-Null

# Build before replacing a healthy container. No down, volume deletion or pruning.
Write-Host 'Building platform images...'
$build = @('build', 'api')
if (-not $ApiOnly) { $build += 'frontend' }
Invoke-PlatformDocker ($compose + $build) | Out-Host
$up = $compose + @('up', '-d', '--no-build', '--wait',
    '--wait-timeout', [string]$WaitTimeoutSeconds)
if ($ApiOnly) {
    $up += @('--no-deps', 'api')
} else {
    $up += @('api', 'frontend')
    if (-not $WithoutN8n) { $up += 'n8n' }
}
Invoke-PlatformDocker $up | Out-Host

$verify = @{ CheckComponents = $CheckComponents; EnvFile = $EnvFile }
if ($ApiOnly) { $verify.ApiOnly = $true }
if ($WithoutN8n) { $verify.WithoutN8n = $true }
& (Join-Path $PSScriptRoot 'check-deployment.ps1') @verify
Write-Host 'Deployment completed and verified.' -ForegroundColor Green
