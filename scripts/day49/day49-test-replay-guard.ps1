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
$evidencePath = Join-Path (Resolve-Path -LiteralPath $EvidenceDirectory).Path "day49-replay-guard-$batchId.json"
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

Save-Evidence
Write-Host "Testing replay protection with NEW simulated records. batch_id=$batchId"
Write-Host 'No n8n execution, model call, or message sending is performed.'
Write-Host "Evidence: $evidencePath"
try {
    $health = Call-Api GET '/health'
    Check ($health.status -eq 'ok') 'API health check failed.'
    foreach ($outcome in @('failed', 'delivery_unknown')) {
        $token = [guid]::NewGuid().ToString('N')
        $eventId = "day49-guard-$token"
        $customerId = "day49-guard-customer-$token"
        $case = [ordered]@{
            scenario = $outcome; event_id = $eventId; customer_id = $customerId
            run_id = $null; followup_id = $null; passed = $false
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
            customer = @{ customer_id = $customerId; company_name = 'Day49 Replay Guard Test'; industry = 'Test'; sales_owner = 'sales-demo' }
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
        Check ($attempt.attempt_number -eq 1 -and $attempt.notification_request_key -eq $key) 'Unexpected notification attempt.'
        $null = Call-Api PATCH "/crm/followups/$followupId/notification" @{ status = $outcome; error_code = "simulated_$outcome" }
        $null = Call-Api PATCH "/workflow-runs/$runId/failure" @{ error_type = "notification_$outcome"; error_message = 'Day49 simulated notification failure'; stage = 'notification' }

        $before = Call-Api GET "/workflow-runs/$runId"
        $followupBefore = Call-Api GET "/crm/workflow-runs/$runId/followup"
        $customerBefore = Call-Api GET "/crm/customers/$customerId"
        $listBefore = Call-Api GET "/crm/customers/$customerId/followups"
        Check ($before.status -eq 'failed' -and $before.processing_stage -eq 'notification_recorded' -and $before.retry_count -eq 0) 'Unexpected initial workflow state.'
        Check ($followupBefore.notification_status -eq $outcome -and $followupBefore.notification_attempt_count -eq 1) 'Unexpected initial notification state.'
        Check ($listBefore.count -eq 1 -and $followupBefore.followup_id -eq $followupId) 'Expected one saved follow-up.'
        $case.before = [ordered]@{ workflow = $before; followup = $followupBefore; customer = $customerBefore; followups = $listBefore }
        Save-Evidence

        $rejected = Call-Api POST '/workflow-runs/start' @{
            event_id = $before.event_id; workflow_name = $before.workflow_name
            source = $before.source; requester = $before.requester
            report_date = [string]$before.report_date; input_data = $before.input_data
            n8n_execution_id = "guard-replay-$token"; replay = $true
        } 409
        Check ($rejected.detail -eq 'CRM already saved; use notification handling instead of replay') '409 came from an unexpected guard.'
        $after = Call-Api GET "/workflow-runs/$runId"
        $followupAfter = Call-Api GET "/crm/workflow-runs/$runId/followup"
        $customerAfter = Call-Api GET "/crm/customers/$customerId"
        $listAfter = Call-Api GET "/crm/customers/$customerId/followups"
        $case.after = [ordered]@{ workflow = $after; followup = $followupAfter; customer = $customerAfter; followups = $listAfter }
        Save-Evidence
        foreach ($recordName in @('workflow', 'followup', 'customer', 'followups')) {
            $beforeJson = $case.before[$recordName] | ConvertTo-Json -Depth 40 -Compress
            $afterJson = $case.after[$recordName] | ConvertTo-Json -Depth 40 -Compress
            Check ($afterJson -ceq $beforeJson) "Replay rejection changed $recordName."
        }
        $recovery = Call-Api GET "/workflow-runs/$runId/recovery"
        $expectedResume = if ($outcome -eq 'delivery_unknown') { 'human_delivery_check' } else { 'notification' }
        Check ($recovery.automatic_retry_allowed -eq $false -and $recovery.requires_human_action -eq $true -and $recovery.resume_from -eq $expectedResume) 'Unexpected recovery policy.'
        Check ($after.retry_count -eq 0 -and $followupAfter.notification_request_key -eq $key -and $listAfter.count -eq 1) 'Retry count, stable key, or follow-up count changed.'
        $case.http_status = 409
        $case.workflow_status = $after.status
        $case.notification_status = $followupAfter.notification_status
        $case.retry_count = $after.retry_count
        $case.notification_attempt_count = $followupAfter.notification_attempt_count
        $case.followup_count = $listAfter.count
        $case.resume_from = $recovery.resume_from
        $case.records_unchanged = $true
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
Write-Host 'Day 49 fresh-data replay guard tests passed.'
$report.cases | ForEach-Object { [pscustomobject]$_ } | Select-Object scenario, event_id, run_id, followup_id, http_status, workflow_status, notification_status, retry_count, notification_attempt_count, followup_count, records_unchanged, passed | ConvertTo-Json -Depth 10
Write-Host 'Test records are retained as evidence. Every rerun creates new records.'
