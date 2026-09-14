param(
    [string]$ApiBaseUrl = 'http://localhost:8000',
    [string]$EvidenceDirectory = (Join-Path $env:TEMP 'day49-acceptance')
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$apiUri = [uri]$ApiBaseUrl
if (-not $apiUri.IsAbsoluteUri -or -not $apiUri.IsLoopback -or $apiUri.Scheme -ne 'http' -or $apiUri.AbsolutePath -ne '/' -or $apiUri.Query -or $apiUri.Fragment -or $apiUri.UserInfo) {
    throw 'ApiBaseUrl must be a local HTTP origin, for example http://localhost:8000.'
}
$api = $ApiBaseUrl.TrimEnd('/')
$batchId = [guid]::NewGuid().ToString('N')
$null = New-Item -ItemType Directory -Force -Path $EvidenceDirectory
$evidencePath = Join-Path (Resolve-Path -LiteralPath $EvidenceDirectory).Path "day49-notification-resolution-$batchId.json"
$report = [ordered]@{
    schema_version = 1
    batch_id = $batchId
    started_at = [DateTime]::UtcNow.ToString('o')
    finished_at = $null
    api_base_url = $api
    validation_mode = 'simulated_state_api'
    passed = $false
    cases = @()
    error = $null
}

function Save-Evidence {
    [System.IO.File]::WriteAllText($evidencePath, ($report | ConvertTo-Json -Depth 40), [System.Text.UTF8Encoding]::new($false))
}
function Check {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}
function Call-Api {
    param([string]$Method, [string]$Path, $Body = $null, [int]$Expected = 200)
    if ($Path -notmatch '^/(health$|openapi\.json$|workflow-runs/|crm/)') {
        throw "Unexpected API path: $Path"
    }
    $requestToken = [guid]::NewGuid().ToString('N')
    $requestFile = Join-Path $env:TEMP "day49-request-$requestToken.json"
    $responseFile = Join-Path $env:TEMP "day49-response-$requestToken.json"
    try {
        $curlArgs = @('--silent', '--show-error', '--noproxy', '*', '--connect-timeout', '5', '--max-time', '20', '--output', $responseFile, '--write-out', '%{http_code}', '--request', $Method)
        if ($null -ne $Body) {
            [System.IO.File]::WriteAllText($requestFile, ($Body | ConvertTo-Json -Depth 40 -Compress), [System.Text.UTF8Encoding]::new($false))
            $curlArgs += @('--header', 'Content-Type: application/json', '--data-binary', "@$requestFile")
        }
        $curlArgs += "$api$Path"
        $httpStatus = & curl.exe @curlArgs
        if ($LASTEXITCODE -ne 0) { throw "Request failed: $Method $Path. Not retried; inspect this batch before rerunning." }
        $responseText = [System.IO.File]::ReadAllText($responseFile, [System.Text.Encoding]::UTF8)
        if ([string]$httpStatus -ne [string]$Expected) {
            throw "Expected HTTP $Expected, got $httpStatus for $Method $Path. Body: $responseText"
        }
        return ($responseText | ConvertFrom-Json)
    } finally {
        foreach ($tempFile in @($requestFile, $responseFile)) {
            if (Test-Path -LiteralPath $tempFile) { Remove-Item -LiteralPath $tempFile -Force }
        }
    }
}

function Assert-RejectedUnchanged {
    param([string]$Method, [string]$Path, $Body, [string]$Label)
    $stateBefore = Call-Api GET "/workflow-runs/$runId"
    $recordBefore = Call-Api GET "/crm/followups/$followupId"
    $null = Call-Api $Method $Path $Body 409
    $stateAfter = Call-Api GET "/workflow-runs/$runId"
    $recordAfter = Call-Api GET "/crm/followups/$followupId"
    Check (($stateBefore | ConvertTo-Json -Depth 40 -Compress) -ceq ($stateAfter | ConvertTo-Json -Depth 40 -Compress)) "$Label changed workflow state."
    Check (($recordBefore | ConvertTo-Json -Depth 40 -Compress) -ceq ($recordAfter | ConvertTo-Json -Depth 40 -Compress)) "$Label changed follow-up state."
    $case.blocked_requests += [ordered]@{ label = $Label; http_status = 409; records_unchanged = $true }
    Save-Evidence
}

Save-Evidence
Write-Host "Testing human notification resolution with NEW simulated records. batch_id=$batchId"
Write-Host 'No n8n execution, model call, or message sending is performed.'
Write-Host "Evidence: $evidencePath"
try {
    $health = Call-Api GET '/health'
    Check ($health.status -eq 'ok') 'API health check failed.'
    foreach ($outcome in @('confirmed_delivered', 'confirmed_not_delivered')) {
        $token = [guid]::NewGuid().ToString('N')
        $eventId = "day49-resolution-$token"
        $customerId = "day49-resolution-customer-$token"
        $case = [ordered]@{
            scenario = $outcome; event_id = $eventId; customer_id = $customerId
            run_id = $null; followup_id = $null; passed = $false; blocked_requests = @()
        }
        $report.cases += $case
        Save-Evidence
        $run = Call-Api POST '/workflow-runs/start' @{
            event_id = $eventId; workflow_name = 'sales-followup-assistant'
            source = 'manual_demo'; requester = 'sales-demo'
            report_date = (Get-Date -Format 'yyyy-MM-dd')
            input_data = @{ customer_id = $customerId; test_scenario = $outcome; batch_id = $batchId }
            n8n_execution_id = "api-simulation-$token"
        }
        $runId = $run.run_id
        $case.run_id = $runId
        Save-Evidence
        Check ($run.should_process -eq $true -and $run.duplicate -eq $false -and $run.retry_count -eq 0) 'Expected a fresh run.'
        Write-Host "Testing $outcome; run_id=$runId"
        $followup = Call-Api POST '/crm/followups' @{
            customer = @{ customer_id = $customerId; company_name = 'Day49 Notification Resolution Test'; industry = 'Test'; sales_owner = 'sales-demo' }
            run_id = $runId; event_id = $eventId
            requirement_snapshot = 'Schedule an internal follow-up meeting.'
            analysis = @{ summary = 'Customer requests a meeting.'; needs = @('Schedule meeting'); missing_information = @(); next_actions = @('Confirm meeting time'); risk_flags = @() }
            priority = 'normal'; review_status = 'not_required'; review_reasons = @()
            notification_mode = 'send'; notification_channel = 'feishu'
        }
        $followupId = $followup.followup_id
        $case.followup_id = $followupId
        Save-Evidence
        $key = $followup.notification_request_key
        Check ($followup.created -eq $true -and $followup.notification_status -eq 'pending') 'Expected a new pending follow-up.'
        Check (-not [string]::IsNullOrWhiteSpace($key)) 'Missing notification request key.'
        $attempt = Call-Api POST "/crm/followups/$followupId/notification-attempts" @{ manual = $false }
        Check ($attempt.attempt_number -eq 1 -and $attempt.notification_request_key -eq $key) 'Unexpected first notification attempt.'
        $null = Call-Api PATCH "/crm/followups/$followupId/notification" @{ status = 'delivery_unknown'; error_code = 'simulated_timeout' }
        $null = Call-Api PATCH "/workflow-runs/$runId/failure" @{ error_type = 'notification_delivery_unknown'; error_message = 'Day49 simulated unknown delivery'; stage = 'notification' }
        $initialWorkflow = Call-Api GET "/workflow-runs/$runId"
        $initialFollowup = Call-Api GET "/crm/followups/$followupId"
        $initialCustomer = Call-Api GET "/crm/customers/$customerId"
        Check ($initialWorkflow.status -eq 'failed' -and $initialWorkflow.processing_stage -eq 'notification_recorded') 'Expected a failed workflow with notification recorded.'
        Check ($initialFollowup.notification_status -eq 'delivery_unknown' -and $initialFollowup.notification_attempt_count -eq 1) 'Expected one unknown notification attempt.'
        $case.before_resolution = [ordered]@{ workflow = $initialWorkflow; followup = $initialFollowup; customer = $initialCustomer }
        Save-Evidence
        foreach ($manual in @($false, $true)) {
            Assert-RejectedUnchanged POST "/crm/followups/$followupId/notification-attempts" @{ manual = $manual } "before_resolution_manual_$manual"
        }
        $delivered = $outcome -eq 'confirmed_delivered'
        $resolutionBody = @{ delivered = $delivered }
        if ($delivered) { $resolutionBody.message_id = "simulated-delivered-$token" }
        $resolved = Call-Api PATCH "/crm/followups/$followupId/notification-resolution" $resolutionBody
        $case.after_resolution = $resolved
        Save-Evidence
        Check ($null -ne $resolved.notification_resolved_at) 'Resolution timestamp missing.'
        Check ($resolved.notification_attempt_count -eq 1 -and $resolved.notification_request_key -eq $key) 'Resolution changed attempt count or request key.'
        Assert-RejectedUnchanged PATCH "/crm/followups/$followupId/notification-resolution" @{ delivered = (-not $delivered) } 'repeat_resolution'
        Assert-RejectedUnchanged POST "/crm/followups/$followupId/notification-attempts" @{ manual = $false } 'automatic_resend_after_resolution'
        if ($delivered) {
            Check ($resolved.notification_status -eq 'sent') 'Confirmed delivery must become sent.'
            Check ($resolved.notification_message_id -eq $resolutionBody.message_id -and $null -eq $resolved.notification_error_code) 'Unexpected confirmed delivery message or error.'
            $expectedCount = 1
            $expectedMessage = $resolutionBody.message_id
        } else {
            Check ($resolved.notification_status -eq 'failed') 'Confirmed non-delivery must become failed.'
            Check ($resolved.notification_error_code -eq 'human_confirmed_not_sent') 'Expected human confirmation error code.'
            $retry = Call-Api POST "/crm/followups/$followupId/notification-attempts" @{ manual = $true }
            Check ($retry.attempt_number -eq 2 -and $retry.manual -eq $true -and $retry.notification_request_key -eq $key) 'Manual retry must register exactly one attempt with a stable key.'
            foreach ($manual in @($false, $true)) {
                Assert-RejectedUnchanged POST "/crm/followups/$followupId/notification-attempts" @{ manual = $manual } "pending_retry_manual_$manual"
            }
            $expectedMessage = "simulated-retry-$token"
            $sentBody = @{ status = 'sent'; message_id = $expectedMessage }
            $sent = Call-Api PATCH "/crm/followups/$followupId/notification" $sentBody
            $resent = Call-Api PATCH "/crm/followups/$followupId/notification" $sentBody
            Check (($sent | ConvertTo-Json -Depth 40 -Compress) -ceq ($resent | ConvertTo-Json -Depth 40 -Compress)) 'Idempotent notification result changed the record.'
            $expectedCount = 2
        }
        foreach ($manual in @($false, $true)) {
            Assert-RejectedUnchanged POST "/crm/followups/$followupId/notification-attempts" @{ manual = $manual } "after_sent_manual_$manual"
        }
        $saved = Call-Api GET "/crm/workflow-runs/$runId/followup"
        $customer = Call-Api GET "/crm/customers/$customerId"
        $list = Call-Api GET "/crm/customers/$customerId/followups"
        $workflow = Call-Api GET "/workflow-runs/$runId"
        $case.final = [ordered]@{ workflow = $workflow; followup = $saved; customer = $customer; followups = $list }
        Save-Evidence
        Check ($saved.followup_id -eq $followupId -and $customer.customer_id -eq $customerId -and $list.count -eq 1) 'CRM data was lost or duplicated.'
        Check ($saved.notification_status -eq 'sent' -and $saved.notification_attempt_count -eq $expectedCount) 'Unexpected final notification status or attempt count.'
        Check ($saved.notification_message_id -eq $expectedMessage -and $null -eq $saved.notification_error_code -and $saved.notification_request_key -eq $key) 'Unexpected final notification message, error, or key.'
        Check (($customer | ConvertTo-Json -Depth 40 -Compress) -ceq ($initialCustomer | ConvertTo-Json -Depth 40 -Compress)) 'Notification handling changed the customer.'
        foreach ($property in $initialFollowup.PSObject.Properties) {
            if ($property.Name.StartsWith('notification_') -or $property.Name -eq 'updated_at') { continue }
            $beforeValue = $property.Value | ConvertTo-Json -Depth 40 -Compress
            $afterValue = $saved.($property.Name) | ConvertTo-Json -Depth 40 -Compress
            Check ($beforeValue -ceq $afterValue) "Notification handling changed CRM business field $($property.Name)."
        }
        Check ($workflow.status -eq 'failed' -and $workflow.processing_stage -eq 'notification_recorded') 'Notification resolution must not silently finish the workflow.'
        Check ($workflow.retry_count -eq 0 -and $workflow.run_id -eq $runId -and $workflow.event_id -eq $eventId) 'Notification handling changed workflow identity or replay count.'
        $case.notification_status = $saved.notification_status
        $case.workflow_status = $workflow.status
        $case.notification_attempt_count = $saved.notification_attempt_count
        $case.retry_count = $workflow.retry_count
        $case.followup_count = $list.count
        $case.request_key_stable = $true
        $case.crm_business_unchanged = $true
        $case.manual_retry_verified = (-not $delivered)
        $case.workflow_completion_pending = $true
        $case.passed = $true
        Save-Evidence
    }
    $report.passed = $true
} catch {
    $report.error = $_.Exception.Message
    throw
} finally {
    $report.finished_at = [DateTime]::UtcNow.ToString('o')
    Save-Evidence
    Write-Host "Evidence saved: $evidencePath"
}
Write-Host 'Day 49 simulated notification resolution tests passed.'
$report.cases | ForEach-Object { [pscustomobject]$_ } | Select-Object scenario, event_id, run_id, followup_id, notification_status, workflow_status, notification_attempt_count, retry_count, followup_count, request_key_stable, crm_business_unchanged, manual_retry_verified, workflow_completion_pending, passed | ConvertTo-Json -Depth 10
Write-Host 'Both notifications are sent in SIMULATED state; both workflows remain failed. No messages were sent.'
Write-Host 'Test records are retained as evidence. Every rerun creates new records.'
