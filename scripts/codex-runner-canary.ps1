param(
    [string]$RedisUrl = "redis://127.0.0.1:6389/0",
    [int]$ApiPort = 8015
)

$ErrorActionPreference = "Stop"
$workspace = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$logDirectory = Join-Path $workspace "logs"
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$runId = Get-Date -Format "yyyyMMdd-HHmmss"
$apiLog = Join-Path $logDirectory "codex-canary-api-$runId.log"
$apiErrorLog = Join-Path $logDirectory "codex-canary-api-$runId.error.log"
$runnerLog = Join-Path $logDirectory "codex-canary-runner-$runId.log"
$runnerErrorLog = Join-Path $logDirectory "codex-canary-runner-$runId.error.log"
$runnerToken = [Convert]::ToBase64String(
    [Security.Cryptography.RandomNumberGenerator]::GetBytes(48)
)
$apiProcess = $null
$runnerProcess = $null

function Stop-ProcessTree {
    param([int]$RootProcessId)

    $children = @(
        Get-CimInstance Win32_Process -Filter "ParentProcessId = $RootProcessId" -ErrorAction SilentlyContinue
    )
    foreach ($child in $children) {
        Stop-ProcessTree -RootProcessId $child.ProcessId
    }
    Stop-Process -Id $RootProcessId -Force -ErrorAction SilentlyContinue
}

$env:APP_ENV = "local"
$env:AI_EXECUTION_MODE = "runner"
$env:CODEX_RUNNER_TOKEN = $runnerToken
$env:CODEX_RUNNER_SERVER_URL = "http://127.0.0.1:$ApiPort"
$env:CODEX_RUNNER_WAIT_TIMEOUT_SECONDS = "120"
$env:REDIS_URL = $RedisUrl
$env:RATE_LIMIT_ENABLED = "false"
$pythonPath = Join-Path $workspace ".venv/Scripts/python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Virtual environment Python was not found. Run 'uv sync --extra dev' first."
}

try {
    $apiProcess = Start-Process `
        -FilePath $pythonPath `
        -ArgumentList @("-m", "uvicorn", "aiwardrobe_api.main:app", "--host", "127.0.0.1", "--port", "$ApiPort") `
        -WorkingDirectory $workspace `
        -WindowStyle Hidden `
        -RedirectStandardOutput $apiLog `
        -RedirectStandardError $apiErrorLog `
        -PassThru

    $live = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $response = Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/health/live" -TimeoutSec 2
            if ($response.status -eq "ok") {
                $live = $true
                break
            }
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $live) {
        throw "The local canary API did not become live."
    }

    $runnerProcess = Start-Process `
        -FilePath $pythonPath `
        -ArgumentList @("scripts/codex-runner.py") `
        -WorkingDirectory $workspace `
        -WindowStyle Hidden `
        -RedirectStandardOutput $runnerLog `
        -RedirectStandardError $runnerErrorLog `
        -PassThru

    $connected = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/health/ai" -TimeoutSec 2
        if ($health.codex_runner_connected) {
            $connected = $true
            break
        }
        Start-Sleep -Milliseconds 500
    }
    if (-not $connected) {
        throw "The local Codex runner did not publish a heartbeat."
    }

    uv run python scripts/codex-relay-canary.py
    if ($LASTEXITCODE -ne 0) {
        throw "The Codex relay canary returned exit code $LASTEXITCODE."
    }
    Write-Output "CANARY_OK api_log=$apiLog runner_log=$runnerLog"
}
finally {
    if ($null -ne $runnerProcess -and -not $runnerProcess.HasExited) {
        Stop-ProcessTree -RootProcessId $runnerProcess.Id
    }
    if ($null -ne $apiProcess -and -not $apiProcess.HasExited) {
        Stop-ProcessTree -RootProcessId $apiProcess.Id
    }
}
