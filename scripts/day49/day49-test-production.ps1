param(
    [string]$ApiBaseUrl = 'http://localhost:8000',
    [string]$N8nBaseUrl = 'http://localhost:5678',
    [string]$EvidenceDirectory = (Join-Path $env:TEMP 'day49-acceptance'),
    [string]$ResumeEvidencePath = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
foreach ($origin in @($ApiBaseUrl, $N8nBaseUrl)) {
    $originUri = [uri]$origin
    if (-not $originUri.IsAbsoluteUri -or -not $originUri.IsLoopback -or $originUri.Scheme -ne 'http' -or $originUri.AbsolutePath -ne '/' -or $originUri.Query -or $originUri.Fragment -or $originUri.UserInfo) {
        throw 'API and n8n URLs must be local HTTP origins.'
    }
}
$api = $ApiBaseUrl.TrimEnd('/')
$n8n = $N8nBaseUrl.TrimEnd('/')
$batchId = [guid]::NewGuid().ToString('N')
$eventId = "day49-production-$batchId"
$customerId = "day49-production-customer-$batchId"
$webhook = '/webhook/w7d47-sales-followup-assistant'
$null = New-Item -ItemType Directory -Force -Path $EvidenceDirectory
$evidencePath = Join-Path (Resolve-Path -LiteralPath $EvidenceDirectory).Path "day49-production-$batchId.json"
$payload = [ordered]@{
    event_id = $eventId; customer_id = $customerId
    company_name = 'Day49 Production Test'; industry = 'Business services'
    requirement = 'Arrange the next internal requirements meeting and confirm the time and attendees. No product, price, or delivery commitments are requested.'
    purchase_window_days = 60; budget_range = $null
    sales_owner = 'sales-demo'; report_date = (Get-Date -Format 'yyyy-MM-dd')
}
$resume = $null
if (-not [string]::IsNullOrWhiteSpace($ResumeEvidencePath)) {
    $resume = Get-Content -LiteralPath $ResumeEvidencePath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($resume.passed -ne $false -or $resume.error -ne 'Response analysis differs from saved CRM analysis.' -or $resume.api_base_url -ne $api -or $resume.n8n_base_url -ne $n8n -or $resume.webhook_path -ne $webhook) {
        throw 'Resume is only supported for this analysis-comparison failure on the same local endpoints.'
    }
    if ($resume.first_response.status -ne 'succeeded' -or $resume.first_response.run_id -ne $resume.run_id -or $resume.before_duplicate.workflow.duplicate_count -ne 0) {
        throw 'Resume evidence must contain the successful first run before duplicate testing.'
    }
    $payload = $resume.input
    $eventId = $payload.event_id
    $customerId = $payload.customer_id
    if ($eventId -ne $resume.event_id -or $customerId -ne $resume.customer_id) { throw 'Resume input identifiers do not match the saved evidence.' }
}
$report = [ordered]@{
    schema_version = 1; batch_id = $batchId
    started_at = [DateTime]::UtcNow.ToString('o'); finished_at = $null
    api_base_url = $api; n8n_base_url = $n8n; webhook_path = $webhook
    validation_mode = 'production_webhook_preview'
    input = $payload; event_id = $eventId; customer_id = $customerId
    run_id = $null; followup_id = $null; passed = $false; error = $null
}
if ($null -ne $resume) {
    $report.resumed_from_batch_id = $resume.batch_id
    $report.first_response_reused = $true
}
function Save-Evidence {
    [System.IO.File]::WriteAllText($evidencePath, ($report | ConvertTo-Json -Depth 40), [System.Text.UTF8Encoding]::new($false))
}
function Check {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}
function ConvertTo-CanonicalJson {
    param([AllowNull()][object]$Value)
    if ($null -eq $Value) { return 'null' }
    if ($Value -is [System.Collections.IDictionary]) {
        $parts = foreach ($key in @($Value.Keys | Sort-Object -CaseSensitive)) {
            (ConvertTo-Json -InputObject ([string]$key) -Compress) + ':' + (ConvertTo-CanonicalJson -Value $Value[$key])
        }
        return '{' + ($parts -join ',') + '}'
    }
    if ($Value -is [pscustomobject]) {
        $parts = foreach ($property in @($Value.PSObject.Properties | Sort-Object Name -CaseSensitive)) {
            (ConvertTo-Json -InputObject $property.Name -Compress) + ':' + (ConvertTo-CanonicalJson -Value $property.Value)
        }
        return '{' + ($parts -join ',') + '}'
    }
    if ($Value -is [System.Collections.IList]) {
        $parts = foreach ($item in $Value) { ConvertTo-CanonicalJson -Value $item }
        return '[' + ($parts -join ',') + ']'
    }
    return ConvertTo-Json -InputObject $Value -Depth 40 -Compress
}
function Call-Api {
    param([string]$Method, [string]$Path, $Body = $null, [string]$BaseUrl = $api, [int]$TimeoutSeconds = 20)
    if (($Method -eq 'POST' -and ($Path -ne $webhook -or $BaseUrl -ne $n8n)) -or ($Method -eq 'GET' -and ($BaseUrl -ne $api -or $Path -notmatch '^/(health$|workflow-runs/|crm/)')) -or $Method -notin @('GET', 'POST')) {
        throw "Unexpected endpoint: $Method $BaseUrl$Path"
    }
    $requestToken = [guid]::NewGuid().ToString('N')
    $requestFile = Join-Path $env:TEMP "day49-request-$requestToken.json"
    $responseFile = Join-Path $env:TEMP "day49-response-$requestToken.json"
    try {
        $curlArgs = @('--silent', '--show-error', '--noproxy', '*', '--connect-timeout', '5', '--max-time', [string]$TimeoutSeconds, '--output', $responseFile, '--write-out', '%{http_code}', '--request', $Method)
        if ($null -ne $Body) {
            [System.IO.File]::WriteAllText($requestFile, ($Body | ConvertTo-Json -Depth 40 -Compress), [System.Text.UTF8Encoding]::new($false))
            $curlArgs += @('--header', 'Content-Type: application/json', '--data-binary', "@$requestFile")
        }
        $curlArgs += "$BaseUrl$Path"
        $httpStatus = & curl.exe @curlArgs
        if ($LASTEXITCODE -ne 0) { throw "Request failed: $Method $Path. Not retried. Inspect event_id=$eventId in n8n before rerunning." }
        $responseText = [System.IO.File]::ReadAllText($responseFile, [System.Text.Encoding]::UTF8)
        if ([string]$httpStatus -ne '200') {
            throw "Expected HTTP 200, got $httpStatus for $Method $Path. Not retried. Body: $responseText"
        }
        return ($responseText | ConvertFrom-Json)
    } finally {
        foreach ($tempFile in @($requestFile, $responseFile)) {
            if (Test-Path -LiteralPath $tempFile) { Remove-Item -LiteralPath $tempFile -Force }
        }
    }
}

Save-Evidence
Write-Host "Testing Production URL; event_id=$eventId"
if ($null -eq $resume) {
    Write-Host 'This invokes the published n8n workflow and its AI model. Notification must remain preview.'
    Write-Host 'No test listener is needed. The first AI analysis may take up to 180 seconds.'
} else {
    Write-Host 'Resuming from the successful first response. Only the existing event duplicate check will be submitted.'
}
Write-Host "Evidence: $evidencePath"
try {
    $health = Call-Api GET '/health'
    Check ($health.status -eq 'ok') 'API health check failed.'
    if ($null -eq $resume) {
        $result = Call-Api POST $webhook $payload $n8n 180
    } else {
        $result = $resume.first_response
    }
    $report.first_response = $result
    Save-Evidence
    Check ($result.duplicate -eq $false) 'Expected a new run.'
    Check (-not [string]::IsNullOrWhiteSpace($result.run_id)) 'Missing run ID.'
    $runId = $result.run_id
    $report.run_id = $runId
    Save-Evidence
    Check ($result.status -eq 'succeeded' -and $result.requires_human_review -eq $false) 'Expected successful normal preview; inspect the saved response and n8n execution.'
    $report.followup_id = $result.followup_id
    Save-Evidence
    Check ($result.customer_id -eq $customerId -and $result.priority -eq 'normal') 'Unexpected customer or priority.'
    Check ($result.notification.mode -eq 'preview' -and $result.notification.status -eq 'preview' -and $result.notification.channel -eq 'feishu') 'Expected Feishu notification preview.'
    Check (-not [string]::IsNullOrWhiteSpace($result.notification.content)) 'Missing preview content.'
    Check ($null -eq $result.notification.message_id) 'Preview must not have a sent message ID.'
    $before = Call-Api GET "/workflow-runs/$runId"
    $followup = Call-Api GET "/crm/workflow-runs/$runId/followup"
    $customer = Call-Api GET "/crm/customers/$customerId"
    $listBefore = Call-Api GET "/crm/customers/$customerId/followups"
    $report.before_duplicate = [ordered]@{ workflow = $before; followup = $followup; customer = $customer; followups = $listBefore }
    Save-Evidence
    Check ($before.status -eq 'succeeded' -and $before.processing_stage -eq 'notification_recorded' -and $before.event_id -eq $eventId) 'Unexpected persisted workflow state.'
    Check ($before.retry_count -eq 0 -and $before.duplicate_count -eq 0) 'Expected a fresh run without retries or duplicates.'
    Check ($null -ne $before.checkpoint_data -and $before.checkpoint_data.run_id -eq $runId -and $before.checkpoint_data.event_id -eq $eventId) 'Checkpoint missing or belongs to another run/event.'
    Check ($followup.followup_id -eq $result.followup_id -and $followup.customer_id -eq $customerId -and $listBefore.count -eq 1) 'CRM record does not match the response or is duplicated.'
    Check ($followup.notification_status -eq 'preview' -and $followup.notification_mode -eq 'preview' -and $followup.notification_attempt_count -eq 0 -and $null -eq $followup.notification_message_id) 'Persisted notification is not an unsent preview.'
    Check ((ConvertTo-CanonicalJson -Value $result.analysis) -ceq (ConvertTo-CanonicalJson -Value $followup.analysis)) 'Response analysis differs from saved CRM analysis.'
    Write-Host 'Submitting the SAME event once more to verify duplicate protection.'
    $duplicate = Call-Api POST $webhook $payload $n8n 180
    $report.duplicate_response = $duplicate
    Save-Evidence
    Check ($duplicate.duplicate -eq $true -and $duplicate.processed -eq $false -and $duplicate.run_id -eq $runId -and $duplicate.event_id -eq $eventId) 'Expected duplicate response with processed=false and original run/event IDs.'
    $after = Call-Api GET "/workflow-runs/$runId"
    $saved = Call-Api GET "/crm/workflow-runs/$runId/followup"
    $customerAfter = Call-Api GET "/crm/customers/$customerId"
    $listAfter = Call-Api GET "/crm/customers/$customerId/followups"
    $report.after_duplicate = [ordered]@{ workflow = $after; followup = $saved; customer = $customerAfter; followups = $listAfter }
    Save-Evidence
    Check ($after.duplicate_count -eq ($before.duplicate_count + 1)) 'Duplicate count did not increase exactly once.'
    foreach ($property in $before.PSObject.Properties) {
        if ($property.Name -in @('duplicate_count', 'updated_at')) { continue }
        Check ((ConvertTo-CanonicalJson -Value $property.Value) -ceq (ConvertTo-CanonicalJson -Value $after.($property.Name))) "Duplicate changed workflow field $($property.Name)."
    }
    foreach ($recordName in @('followup', 'customer', 'followups')) {
        Check ((ConvertTo-CanonicalJson -Value $report.before_duplicate[$recordName]) -ceq (ConvertTo-CanonicalJson -Value $report.after_duplicate[$recordName])) "Duplicate changed $recordName."
    }
    Check ($listAfter.count -eq 1 -and $saved.notification_attempt_count -eq 0) 'Duplicate created a follow-up or notification attempt.'
    $report.summary = [ordered]@{
        event_id = $eventId; run_id = $runId; followup_id = $saved.followup_id
        workflow_status = $after.status; processing_stage = $after.processing_stage
        checkpoint_saved = $true; notification_status = $saved.notification_status
        notification_attempt_count = $saved.notification_attempt_count
        duplicate_blocked = $true; duplicate_count = $after.duplicate_count
        retry_count = $after.retry_count; followup_count = $listAfter.count
        crm_unchanged = $true
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
Write-Host 'Day 49 Production URL and duplicate tests passed.'
$report.summary | ConvertTo-Json -Depth 10
Write-Host 'Production HTTP and persistence acceptance is complete. No additional node review is required for this check.'
Write-Host 'Test records are retained. Each new script run uses a new event.'
