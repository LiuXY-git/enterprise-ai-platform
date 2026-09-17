[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$BundleDirectory,
    [Parameter(Mandatory = $true)]
    [ValidateSet('01-customer', '02-email-review', '03-sales', '04-sales-duplicate')]
    [string]$Step,
    [ValidateRange(5, 300)][int]$TimeoutSeconds = 180
)

$ErrorActionPreference = 'Stop'
$bundle = (Resolve-Path -LiteralPath $BundleDirectory).Path
$manifest = Get-Content -LiteralPath (Join-Path $bundle 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$entry = @($manifest.steps | Where-Object { $_.step -eq $Step })
$fileName = "$Step.request.json"
if ($manifest.schema_version -ne 1 -or $entry.Count -ne 1 -or $entry[0].request_file -ne $fileName) {
    throw 'Invalid demo manifest or step.'
}
$requestPath = Join-Path $bundle $fileName
if ((Get-FileHash -LiteralPath $requestPath -Algorithm SHA256).Hash -ne $entry[0].sha256) {
    throw 'Request changed after preparation. Inspect the bundle before continuing.'
}
$request = Get-Content -LiteralPath $requestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$uri = [uri]$request.url
$webhooks = @{
    '01-customer' = 'w6d38-ai-customer-request'
    '02-email-review' = 'w6d41-persistent-ai-email-assistant'
    '03-sales' = 'w7d47-sales-followup-assistant'
    '04-sales-duplicate' = 'w7d47-sales-followup-assistant'
}
$expectedPath = '^/webhook(?:-test)?/' + [regex]::Escape($webhooks[$Step]) + '$'
if ($request.method -ne 'POST' -or $null -eq $request.body -or
    -not $uri.IsAbsoluteUri -or $uri.Scheme -ne 'http' -or
    $uri.Host -notin @('localhost', '127.0.0.1') -or $uri.UserInfo -or $uri.Fragment -or
    $uri.AbsolutePath -notmatch $expectedPath -or $request.url -ne $entry[0].url) {
    throw 'Only the expected local HTTP n8n webhook is supported.'
}

if ($Step -eq '04-sales-duplicate') {
    $salesPath = Join-Path $bundle '03-sales.request.json'
    if ((Get-FileHash -LiteralPath $salesPath -Algorithm SHA256).Hash -ne $entry[0].sha256) {
        throw 'Duplicate request must exactly match the original sales request.'
    }
    $first = Get-Content -LiteralPath (Join-Path $bundle '03-sales.result.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($first.batch_id -ne $manifest.batch_id -or $first.status -ne 'response_received_unverified' -or
        $first.response.status -ne 'succeeded' -or -not $first.response.run_id -or
        -not $first.response.followup_id -or $first.response.requires_human_review -ne $false -or
        $first.response.notification.mode -ne 'preview' -or
        $first.response.notification.status -ne 'preview') {
        throw 'Inspect the original sales result before attempting the duplicate demonstration.'
    }
}

$resultPath = Join-Path $bundle "$Step.result.json"
$record = [ordered]@{
    schema_version = 1
    batch_id = $manifest.batch_id
    step = $Step
    started_at = [DateTime]::UtcNow.ToString('o')
    finished_at = $null
    status = 'request_started'
    url = $request.url
    input = $request.body
    response = $null
    business_verified = $false
}
$encoding = [System.Text.UTF8Encoding]::new($false)
$pending = $encoding.GetBytes(($record | ConvertTo-Json -Depth 40))
# An existing result (including a failed or interrupted request) blocks a resend.
$stream = [System.IO.File]::Open($resultPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write)
try { $stream.Write($pending, 0, $pending.Length) } finally { $stream.Dispose() }
Write-Host "Result file: $resultPath"
try {
    $payload = $request.body | ConvertTo-Json -Depth 30 -Compress
    $record.response = Invoke-RestMethod -Method Post -Uri $uri.AbsoluteUri `
        -ContentType 'application/json; charset=utf-8' `
        -Headers @{ 'X-Client-Name' = 'day55-recording-demo' } `
        -Body ($encoding.GetBytes($payload)) -TimeoutSec $TimeoutSeconds -MaximumRedirection 0
    $record.status = 'response_received_unverified'
} catch {
    $record.status = 'request_failed_or_unknown'
    throw 'Request failed or timed out. Inspect the saved event and n8n execution; do not delete the result file to retry.'
} finally {
    $record.finished_at = [DateTime]::UtcNow.ToString('o')
    [System.IO.File]::WriteAllText($resultPath, ($record | ConvertTo-Json -Depth 40), $encoding)
}
$record.response | ConvertTo-Json -Depth 30
Write-Host 'HTTP response saved. Verify business fields and persistent records before marking the step passed.'
