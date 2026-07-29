param(
    [string]$EnvFile = ".env.runner.local"
)

$ErrorActionPreference = "Stop"
$workspace = Split-Path -Parent $PSScriptRoot
$resolvedEnv = [System.IO.Path]::GetFullPath((Join-Path $workspace $EnvFile))
if (-not $resolvedEnv.StartsWith($workspace, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Runner environment file must stay inside the workspace."
}
if (-not (Test-Path -LiteralPath $resolvedEnv)) {
    throw "Runner environment file was not found: $resolvedEnv"
}

foreach ($line in [System.IO.File]::ReadAllLines($resolvedEnv)) {
    if ([string]::IsNullOrWhiteSpace($line) -or $line.TrimStart().StartsWith("#")) {
        continue
    }
    $parts = $line.Split("=", 2)
    if ($parts.Length -ne 2) {
        throw "Invalid runner environment line."
    }
    [System.Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1], "Process")
}

$logDirectory = Join-Path $workspace "logs"
[System.IO.Directory]::CreateDirectory($logDirectory) | Out-Null
$stdoutPath = Join-Path $logDirectory "codex-runner.out.log"
$stderrPath = Join-Path $logDirectory "codex-runner.err.log"
$pidPath = Join-Path $logDirectory "codex-runner.pid"
$pythonPath = Join-Path $workspace ".venv/Scripts/python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Virtual environment Python was not found. Run 'uv sync --extra dev' first."
}

if (Test-Path -LiteralPath $pidPath) {
    $existingPid = 0
    if ([int]::TryParse([System.IO.File]::ReadAllText($pidPath).Trim(), [ref]$existingPid)) {
        $existingProcess = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
        if ($null -ne $existingProcess) {
            Write-Output "Codex runner is already running with PID $existingPid."
            return
        }
    }
}

$process = Start-Process `
    -FilePath $pythonPath `
    -ArgumentList @("scripts/codex-runner.py") `
    -WorkingDirectory $workspace `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -PassThru

[System.IO.File]::WriteAllText($pidPath, [string]$process.Id)
Write-Output "Codex runner started with PID $($process.Id)."
