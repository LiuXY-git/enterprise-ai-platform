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

Write-Host 'Testing simulated human notification resolution. No messages are sent.'
$results = @()
foreach ($outcome in @('confirmed_delivered', 'confirmed_not_delivered')) {
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
    Check ($attempt.attempt_number -eq 1) 'Expected first attempt.'
    $null = Call-Api PATCH "/crm/followups/$followupId/notification" @{ status = 'delivery_unknown'; error_code = 'simulated_timeout' }
    $null = Call-Api PATCH "/workflow-runs/$runId/failure" @{ error_type = 'notification_delivery_unknown'; error_message = 'Simulated unknown delivery'; stage = 'notification' }
    foreach ($manual in @($false, $true)) {
        $null = Call-Api POST "/crm/followups/$followupId/notification-attempts" @{ manual = $manual } 409
    }
    $delivered = $outcome -eq 'confirmed_delivered'
    $resolutionBody = @{ delivered = $delivered }
    if ($delivered) { $resolutionBody.message_id = "simulated-delivered-$token" }
    $resolved = Call-Api PATCH "/crm/followups/$followupId/notification-resolution" $resolutionBody
    Check ($null -ne $resolved.notification_resolved_at) 'Resolution timestamp missing.'
    Check ($resolved.notification_attempt_count -eq 1) 'Resolution changed the attempt count.'
    Check ($resolved.notification_request_key -eq $key) 'Resolution changed request key.'
    $null = Call-Api PATCH "/crm/followups/$followupId/notification-resolution" @{ delivered = (-not $delivered) } 409
    $null = Call-Api POST "/crm/followups/$followupId/notification-attempts" @{ manual = $false } 409
    if ($delivered) {
        Check ($resolved.notification_status -eq 'sent') 'Confirmed delivery must become sent.'
        Check ($resolved.notification_message_id -eq $resolutionBody.message_id) 'Confirmed message ID was lost.'
        Check ($null -eq $resolved.notification_error_code) 'Delivery confirmation must clear error code.'
        $expectedCount = 1
        $expectedMessage = $resolutionBody.message_id
    } else {
        Check ($resolved.notification_status -eq 'failed') 'Confirmed non-delivery must become failed.'
        Check ($resolved.notification_error_code -eq 'human_confirmed_not_sent') 'Expected human confirmation error code.'
        $retry = Call-Api POST "/crm/followups/$followupId/notification-attempts" @{ manual = $true }
        Check ($retry.attempt_number -eq 2 -and $retry.manual -eq $true) 'Manual retry was not registered exactly once.'
        Check ($retry.notification_request_key -eq $key) 'Manual retry changed request key.'
        foreach ($manual in @($false, $true)) {
            $null = Call-Api POST "/crm/followups/$followupId/notification-attempts" @{ manual = $manual } 409
        }
        $expectedMessage = "simulated-retry-$token"
        $sentBody = @{ status = 'sent'; message_id = $expectedMessage }
        $null = Call-Api PATCH "/crm/followups/$followupId/notification" $sentBody
        $null = Call-Api PATCH "/crm/followups/$followupId/notification" $sentBody
        $expectedCount = 2
    }
    foreach ($manual in @($false, $true)) {
        $null = Call-Api POST "/crm/followups/$followupId/notification-attempts" @{ manual = $manual } 409
    }
    $saved = Call-Api GET "/crm/workflow-runs/$runId/followup"
    $customer = Call-Api GET "/crm/customers/$customerId"
    $list = Call-Api GET "/crm/customers/$customerId/followups"
    Check ($saved.followup_id -eq $followupId -and $customer.customer_id -eq $customerId -and $list.count -eq 1) 'CRM data was lost or duplicated.'
    Check ($saved.notification_status -eq 'sent' -and $saved.notification_attempt_count -eq $expectedCount) 'Unexpected final notification state.'
    Check ($saved.notification_message_id -eq $expectedMessage -and $null -eq $saved.notification_error_code) 'Unexpected final message or error.'
    Check ($saved.notification_request_key -eq $key) 'Stable request key was lost.'
    $results += [ordered]@{
        scenario = $outcome; run_id = $runId; followup_id = $followupId
        notification_status = $saved.notification_status; attempt_count = $saved.notification_attempt_count
        crm_preserved = $true; request_key_stable = $true
        resend_before_resolution_blocked = $true; automatic_resend_blocked = $true
        manual_retry_verified = (-not $delivered); resend_after_sent_blocked = $true
    }
}
Write-Host 'Day 48 simulated notification resolution API tests passed.'
$results | ConvertTo-Json -Depth 10