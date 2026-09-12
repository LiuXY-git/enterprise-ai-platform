$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$api = 'http://localhost:8000'

function Call-Api {
    param([string]$Method, [string]$Path, $Body = $null, [int]$Expected = 200, [string]$BaseUrl = $api)
    $token = [guid]::NewGuid().ToString('N')
    $requestFile = Join-Path $env:TEMP "day48-notification-request-$token.json"
    $responseFile = Join-Path $env:TEMP "day48-notification-response-$token.json"
    try {
        $curlArgs = @('--silent', '--show-error', '--max-time', '180', '--output', $responseFile, '--write-out', '%{http_code}', '--request', $Method)
        if ($null -ne $Body) {
            [System.IO.File]::WriteAllText($requestFile, ($Body | ConvertTo-Json -Depth 30 -Compress), [System.Text.UTF8Encoding]::new($false))
            $curlArgs += @('--header', 'Content-Type: application/json', '--data-binary', "@$requestFile")
        }
        $curlArgs += "$BaseUrl$Path"
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

$token = [guid]::NewGuid().ToString('N')
$eventId = "day48-production-$token"
$customerId = "day48-production-customer-$token"
$payload = @{
    event_id = $eventId
    customer_id = $customerId
    company_name = 'Day48 Production Test'
    industry = 'Business services'
    requirement = 'Arrange the next internal requirements meeting and confirm the time and attendees. No product, price, or delivery commitments are requested.'
    purchase_window_days = 60
    budget_range = $null
    sales_owner = 'sales-demo'
    report_date = (Get-Date -Format 'yyyy-MM-dd')
}
$webhook = '/webhook/w7d47-sales-followup-assistant'
Write-Host "Testing Production URL; event_id=$eventId. AI analysis may take up to 180 seconds."
$result = Call-Api POST $webhook $payload 200 'http://localhost:5678'
Check ($result.duplicate -eq $false) 'Expected a new run.'
Check (-not [string]::IsNullOrWhiteSpace($result.run_id)) 'Missing run ID.'
Check ($result.status -eq 'succeeded' -and $result.requires_human_review -eq $false) 'Expected successful notification preview; inspect the AI response.'
Check ($result.notification.mode -eq 'preview' -and $result.notification.status -eq 'preview') 'Expected preview mode.'
Check (-not [string]::IsNullOrWhiteSpace($result.notification.content)) 'Missing preview content.'
$runId = $result.run_id
$before = Call-Api GET "/workflow-runs/$runId"
$followup = Call-Api GET "/crm/workflow-runs/$runId/followup"
Check ($before.status -eq 'succeeded' -and $before.processing_stage -eq 'notification_recorded') 'Unexpected persisted run state.'
Check ($null -ne $before.checkpoint_data -and $before.checkpoint_data.run_id -eq $runId) 'Day 48 checkpoint missing or belongs to a different run.'
Check ($followup.followup_id -eq $result.followup_id -and $followup.customer_id -eq $customerId) 'CRM record does not match response.'
Check ($followup.notification_attempt_count -eq 0) 'Preview unexpectedly registered a sending attempt.'
$beforeCheckpoint = $before.checkpoint_data | ConvertTo-Json -Depth 40 -Compress
$beforeFollowup = $followup | ConvertTo-Json -Depth 40 -Compress
Write-Host 'Testing the same event again for duplicate protection.'
$duplicate = Call-Api POST $webhook $payload 200 'http://localhost:5678'
Check ($duplicate.duplicate -eq $true -and $duplicate.run_id -eq $runId) 'Expected duplicate response with the original run ID.'
$after = Call-Api GET "/workflow-runs/$runId"
$saved = Call-Api GET "/crm/workflow-runs/$runId/followup"
$list = Call-Api GET "/crm/customers/$customerId/followups"
Check ($after.status -eq 'succeeded' -and $after.retry_count -eq 0) 'Duplicate changed run status or retry count.'
Check ($after.duplicate_count -eq ($before.duplicate_count + 1)) 'Duplicate count did not increase exactly once.'
Check (($after.checkpoint_data | ConvertTo-Json -Depth 40 -Compress) -ceq $beforeCheckpoint) 'Duplicate changed checkpoint.'
Check (($saved | ConvertTo-Json -Depth 40 -Compress) -ceq $beforeFollowup) 'Duplicate changed CRM record.'
Check ($list.count -eq 1) 'Duplicate created another CRM follow-up.'
Write-Host 'Day 48 Production URL and duplicate tests passed.'
[ordered]@{
    event_id = $eventId; run_id = $runId; followup_id = $saved.followup_id
    workflow_status = $after.status; processing_stage = $after.processing_stage
    checkpoint_saved = $true; notification_status = $saved.notification_status
    duplicate_blocked = $true; duplicate_count = $after.duplicate_count
    followup_count = $list.count; crm_unchanged = $true
} | ConvertTo-Json -Depth 10