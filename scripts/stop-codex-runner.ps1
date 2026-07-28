$ErrorActionPreference = "Stop"
$workspace = Split-Path -Parent $PSScriptRoot
$pidPath = Join-Path $workspace "logs/codex-runner.pid"
if (-not (Test-Path -LiteralPath $pidPath)) {
    Write-Output "Codex runner PID file is absent."
    exit 0
}

$runnerPid = [int]([System.IO.File]::ReadAllText($pidPath).Trim())
$process = Get-CimInstance Win32_Process -Filter "ProcessId = $runnerPid" -ErrorAction SilentlyContinue
if ($null -eq $process) {
    [System.IO.File]::Delete($pidPath)
    Write-Output "Codex runner is already stopped."
    exit 0
}

if ($process.Name -notin @("python.exe", "pythonw.exe") -or $process.CommandLine -notmatch "codex-runner\.py") {
    throw "PID $runnerPid does not belong to a recognized runner process."
}

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

Stop-ProcessTree -RootProcessId $runnerPid
[System.IO.File]::Delete($pidPath)
Write-Output "Codex runner stopped."
