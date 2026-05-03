param(
    [string]$ApiUrl = "http://localhost:8000",
    [string]$MiniAppUrl = "http://localhost:5173"
)

$ErrorActionPreference = "Stop"

function Test-HttpJson {
    param([string]$Url)

    try {
        return Invoke-RestMethod -Uri $Url -TimeoutSec 10
    }
    catch {
        throw "Cannot reach $Url. Check docker compose logs and whether the host port is already occupied."
    }
}

$root = Test-HttpJson "$ApiUrl/"
if ($root.name -ne "AI Digital Wardrobe API") {
    throw "Unexpected API root response at $ApiUrl. Another service may be bound to this port."
}

$health = Test-HttpJson "$ApiUrl/health"
if ($health.status -ne "ok") {
    throw "API health is not ok."
}

try {
    $mini = Invoke-WebRequest -Uri $MiniAppUrl -TimeoutSec 10
}
catch {
    throw "Cannot reach Mini App at $MiniAppUrl. Check miniapp service logs and port bindings."
}

if ($mini.StatusCode -ne 200) {
    throw "Mini App returned HTTP $($mini.StatusCode)."
}

Write-Output "Smoke check passed: API=$ApiUrl MiniApp=$MiniAppUrl"
