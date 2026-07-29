param(
    [string]$TaskName = "AI Wardrobe Codex Runner"
)

$ErrorActionPreference = "Stop"
$workspace = Split-Path -Parent $PSScriptRoot
$startScript = Join-Path $PSScriptRoot "start-codex-runner.ps1"
if (-not (Test-Path -LiteralPath $startScript)) {
    throw "Runner start script was not found: $startScript"
}

$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$taskAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$startScript`"" `
    -WorkingDirectory $workspace
$taskTrigger = New-ScheduledTaskTrigger -AtLogOn -User $currentUser
$taskSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $taskAction `
    -Trigger $taskTrigger `
    -Settings $taskSettings `
    -Description "Starts the trusted local AI Wardrobe Codex relay after Windows logon." `
    -Force | Out-Null

Write-Output "Scheduled task '$TaskName' is installed for $currentUser."
