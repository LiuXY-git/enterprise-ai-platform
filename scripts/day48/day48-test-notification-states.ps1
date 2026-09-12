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

Write-Host 'Testing Day 48 notification state APIs with simulated results. No messages are sent.'
$results = @()
foreach ($outcome in @('failed', 'delivery_unknown')) {
    $token = [guid]::NewGuid().ToString('N')
    $eventId = "day48-notification-$token"
    $customerId = "day48-notification-customer-$token"
    $run = Call-Api POST '/workflow-runs/start' @{
        event_id = $eventId
        workflow_name = 'sales-followup-assistant'
        source = 'manual_demo'
        requester = 'sales-demo'
        report_date = (Get-Date -Format 'yyyy-MM-dd')
        input_data = @{ customer_id = $customerId; test_scenario = $outcome }
        n8n_execution_id = "api-simulation-$token"
    }
    $runId = $run.run_id
    Check ($run.should_process -eq $true) 'Expected a new run.'
    Write-Host "Testing $outcome; run_id=$runId"
    $followup = Call-Api POST '/crm/followups' @{
        customer = @{ customer_id = $customerId; company_name = 'Day48 Notification Test'; industry = 'Test'; sales_owner = 'sales-demo' }
        run_id = $runId
        event_id = $eventId
        requirement_snapshot = 'Schedule an internal follow-up meeting.'
        analysis = @{ summary = 'Customer requests a meeting.'; needs = @('Schedule meeting'); missing_information = @(); next_actions = @('Confirm meeting time'); risk_flags = @() }
        priority = 'normal'
        review_status = 'not_required'
        review_reasons = @()
        notification_mode = 'send'
        notification_channel = 'feishu'
    }
    $followupId = $followup.followup_id
    $key = $followup.notification_request_key
    Check ($followup.created -eq $true -and $followup.notification_status -eq 'pending') 'Expected new pending follow-up.'
    Check (-not [string]::IsNullOrWhiteSpace($key)) 'Missing stable request key.'
    $attempt = Call-Api POST "/crm/followups/$followupId/notification-attempts" @{ manual = $false }
    Check ($attempt.attempt_number -eq 1 -and $attempt.notification_request_key -eq $key) 'Unexpected first attempt.'
    $null = Call-Api POST "/crm/followups/$followupId/notification-attempts" @{ manual = $false } 409
    $resultBody = @{ status = $outcome; error_code = "simulated_$outcome" }
    $null = Call-Api PATCH "/crm/followups/$followupId/notification" $resultBody
    $null = Call-Api PATCH "/crm/followups/$followupId/notification" $resultBody
    $null = Call-Api PATCH "/workflow-runs/$runId/failure" @{ error_type = "notification_$outcome"; error_message = 'Simulated notification result for acceptance testing'; stage = 'notification' }
    $null = Call-Api POST "/crm/followups/$followupId/notification-attempts" @{ manual = $false } 409
    if ($outcome -eq 'delivery_unknown') {
        $null = Call-Api POST "/crm/followups/$followupId/notification-attempts" @{ manual = $true } 409
    }
    $saved = Call-Api GET "/crm/workflow-runs/$runId/followup"
    $customer = Call-Api GET "/crm/customers/$customerId"
    $list = Call-Api GET "/crm/customers/$customerId/followups"
    $state = Call-Api GET "/workflow-runs/$runId"
    $recovery = Call-Api GET "/workflow-runs/$runId/recovery"
    Check ($saved.followup_id -eq $followupId -and $customer.customer_id -eq $customerId -and $list.count -eq 1) 'CRM data was lost or duplicated.'
    Check ($saved.notification_status -eq $outcome -and $saved.notification_attempt_count -eq 1) 'Unexpected notification state or duplicate attempt.'
    Check ($saved.notification_request_key -eq $key) 'Notification request key changed.'
    Check ($state.status -eq 'failed' -and $state.processing_stage -eq 'notification_recorded') 'Unexpected workflow state.'
    Check ($recovery.automatic_retry_allowed -eq $false -and $recovery.requires_human_action -eq $true) 'Recovery must require human action.'
    $expectedResume = if ($outcome -eq 'delivery_unknown') { 'human_delivery_check' } else { 'notification' }
    Check ($recovery.resume_from -eq $expectedResume) 'Unexpected recovery route.'
    $results += [ordered]@{
        scenario = $outcome; run_id = $runId; followup_id = $followupId
        notification_status = $saved.notification_status; crm_preserved = $true
        attempt_count = $saved.notification_attempt_count; request_key_stable = $true
        automatic_retry_blocked = $true; resume_from = $recovery.resume_from
    }
}
Write-Host 'Day 48 notification state API tests passed.'
$results | ConvertTo-Json -Depth 10
