Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-PlatformDocker {
    param([Parameter(Mandatory = $true)][string[]]$DockerArguments)
    $result = & docker @DockerArguments
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker command failed. Deployment stopped; existing data is retained.'
    }
    return $result
}

function Get-PlatformComposeArguments {
    param([Parameter(Mandatory = $true)][string]$ProjectRoot)
    return @('compose', '--project-directory', $ProjectRoot,
        '-f', (Join-Path $ProjectRoot 'compose.yaml'))
}

function Test-PlatformDocker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw 'Docker CLI is missing. Install/start Docker Desktop first.'
    }
    $version = (Invoke-PlatformDocker @('compose', 'version', '--short') | Out-String).Trim()
    if ($version -notmatch '^v?(\d+\.\d+\.\d+)') {
        throw 'Cannot determine Docker Compose version.'
    }
    if ([version]$Matches[1] -lt [version]'2.20.0') {
        throw 'Docker Compose 2.20.0 or later is required.'
    }
    Invoke-PlatformDocker @('info', '--format', '{{.ServerVersion}}') | Out-Null
}

function Get-PlatformContainer {
    param([string[]]$ComposeArguments, [string]$Service)
    $ids = @(Invoke-PlatformDocker ($ComposeArguments + @('ps', '-q', $Service)))
    if ($ids.Count -ne 1 -or [string]::IsNullOrWhiteSpace($ids[0])) {
        throw "Expected one running $Service container in this Compose project."
    }
    return $ids[0].Trim()
}

function Assert-PlatformHealthy {
    param([string]$ContainerId, [string]$Service)
    $state = (Invoke-PlatformDocker @('inspect', '--format',
        '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}',
        $ContainerId) | Out-String).Trim()
    if ($state -ne 'running healthy') {
        throw "$Service is not healthy: $state"
    }
}

function Assert-PlatformBind {
    param([object[]]$Mounts, [string]$Destination, [string]$Source)
    $found = @($Mounts | Where-Object { $_.Destination -eq $Destination })
    if ($found.Count -ne 1 -or $found[0].Type -ne 'bind' -or -not $found[0].RW) {
        throw "Missing writable bind mount: $Destination"
    }
    # Docker Desktop reports Windows host paths; accept slash variants.
    $actual = [IO.Path]::GetFullPath($found[0].Source.Replace('/', '\')).TrimEnd('\')
    $expected = [IO.Path]::GetFullPath($Source).TrimEnd('\')
    if (-not [string]::Equals($actual, $expected, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Unexpected host directory mounted at $Destination"
    }
}
