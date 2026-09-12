$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$api = 'http://localhost:8000'

function Call-Api {
    param([string]$Method, [string]$Path, $Body = $null, [int]$Expected = 200)
    $token = [guid]::NewGuid().ToString('N')
    $requestFile = Join-Path $env:TEMP "day48-notification-request-$token.json"
    $responseFile = Join-Path $env:TEMP "day48-notification-response-$token.json"
    try {
        $curlArgs = @('--silent', '--show-error', '--max-time', '20', '--output', $responseFile, '--write-out', '%{http_code}', '--request', $Method)
        if ($null -ne $Body) {
            [System.IO.File]::WriteAllText($requestFile, ($Body | ConvertTo-Json -Depth 30 -Compress), [System.Text.UTF8Encoding]::new($false))
            $curlArgs += @('--header', 'Content-Type: application/json', '--data-binary', "@$requestFile")
        }
        $curlArgs += "$api$Path"
        $status = & curl.exe @curlArgs
        if ($LASTEXITCODE -ne 0) { throw "Request failed: $Method $Path. Not retried." }
        $text = [System.IO.File]::ReadAllText($responseFile, [System.Text.Encoding]::UTF8)
        if ([string]$status -ne [string]$Expected) { throw "Expected HTTP $Expected, got $status for $Method $Path. Body: $text" }
        return ($text | ConvertFrom-Json)
    } finally {
        foreach ($tempFile in @($requestFile, $responseFile)) {
            if (Test-Path -LiteralPath $tempFile) { Remove-Item -LiteralPath $tempFile -Force }
        }
    }
}
function Check {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

Write-Host 'Testing deployed replay guard. No messages are sent.'
$cases = @(
    @{ run_id = '1cd2de32-4afd-4b85-b140-2990da9db654'; notification_status = 'failed' },
    @{ run_id = '4e82b6bd-076d-4081-b887-b5ff513bd273'; notification_status = 'delivery_unknown' }
)
$results = @()
foreach ($case in $cases) {
    $runId = $case.run_id
    $before = Call-Api GET "/workflow-runs/$runId"
    $followupBefore = Call-Api GET "/crm/workflow-runs/$runId/followup"
    Check ($before.status -eq 'failed') 'Test run must still be failed.'
    Check ($before.processing_stage -eq 'notification_recorded') 'Unexpected processing stage.'
    Check ($before.retry_count -eq 0) 'Unexpected retry count; stop to inspect the test record.'
    Check ($followupBefore.notification_status -eq $case.notification_status) 'Notification state changed; stop to inspect the test record.'
    $beforeJson = $before | ConvertTo-Json -Depth 40 -Compress
    $followupBeforeJson = $followupBefore | ConvertTo-Json -Depth 40 -Compress
    $payload = @{
        event_id = $before.event_id
        workflow_name = $before.workflow_name
        source = $before.source
        requester = $before.requester
        report_date = [string]$before.report_date
        input_data = $before.input_data
        n8n_execution_id = ('guard-test-' + [guid]::NewGuid().ToString('N'))
        replay = $true
    }
    $rejected = Call-Api POST '/workflow-runs/start' $payload 409
    Check ($rejected.detail -eq 'CRM already saved; use notification handling instead of replay') '409 came from an unexpected guard.'
    $after = Call-Api GET "/workflow-runs/$runId"
    $followupAfter = Call-Api GET "/crm/workflow-runs/$runId/followup"
    $afterJson = $after | ConvertTo-Json -Depth 40 -Compress
    $followupAfterJson = $followupAfter | ConvertTo-Json -Depth 40 -Compress
    Check ($afterJson -ceq $beforeJson) 'Replay rejection changed the workflow record.'
    Check ($followupAfterJson -ceq $followupBeforeJson) 'Replay rejection changed the follow-up record.'
    $recovery = Call-Api GET "/workflow-runs/$runId/recovery"
    Check ($recovery.automatic_retry_allowed -eq $false -and $recovery.requires_human_action -eq $true) 'Recovery policy does not require human action.'
    $results += [ordered]@{
        run_id = $runId
        notification_status = $followupAfter.notification_status
        http_status = 409
        workflow_unchanged = $true
        followup_unchanged = $true
        retry_count = $after.retry_count
        automatic_replay_blocked = $true
    }
}
Write-Host 'Day 48 deployed replay guard tests passed.'
$results | ConvertTo-Json -Depth 10