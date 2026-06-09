# Hive OS — Windows install (no Docker).
# Builds the app, then registers a Scheduled Task that runs the server at logon
# (auto-start, restart on failure). Re-runnable. Run in PowerShell:
#   powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1
$ErrorActionPreference = "Stop"

$Root   = (Resolve-Path "$PSScriptRoot\..").Path
$ApiDir = Join-Path $Root "apps\api"
$WebDir = Join-Path $Root "apps\web"
$TaskName = "HiveOS"

function Need($cmd) {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
    Write-Error "missing required command: $cmd"
  }
}
Need uv; Need npm

Write-Host "==> Building backend deps"
Push-Location $ApiDir; uv sync; Pop-Location

Write-Host "==> Building web PWA"
Push-Location $WebDir; npm install; npm run build; Pop-Location

Write-Host "==> Checking for an agent runner"
$haveAgent = (Get-Command claude -ErrorAction SilentlyContinue) -or `
             (Get-Command codex  -ErrorAction SilentlyContinue) -or `
             (Get-Command hermes -ErrorAction SilentlyContinue)
if ($haveAgent) {
  Write-Host "    Found an agent CLI - Hive will use your existing install(s)."
} else {
  Write-Warning "no agent CLI (claude/codex/hermes) found. Hive installs fine, but chats"
  Write-Warning "won't run until you install + log into one (e.g. 'claude /login')."
}

# The server is launched via `uv run python apps\api\scripts\serve.py` so uv
# manages the venv interpreter cross-platform.
$uv = (Get-Command uv).Source
$serve = Join-Path $ApiDir "scripts\serve.py"
$logDir = Join-Path $env:LOCALAPPDATA "hive-os\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

Write-Host "==> Registering scheduled task '$TaskName' (runs at logon)"
# A small launcher cmd so output is captured and the working dir is correct.
$runner = Join-Path $env:LOCALAPPDATA "hive-os\run-server.cmd"
@"
@echo off
cd /d "$ApiDir"
"$uv" run python "$serve" >> "$logDir\hive-os.log" 2>&1
"@ | Set-Content -Encoding ASCII $runner

$action    = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$runner`""
$trigger   = New-ScheduledTaskTrigger -AtLogOn
$settings  = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName

$port = if ($env:HIVEOS_PORT) { $env:HIVEOS_PORT } else { "8765" }
Write-Host ""
Write-Host "Hive OS is installed and running (Scheduled Task '$TaskName')." -ForegroundColor Green
Write-Host "   Open:     http://127.0.0.1:$port   (first launch asks you to create the admin account)"
Write-Host "   Update:   git pull; powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1"
Write-Host "   Logs:     Get-Content `"$logDir\hive-os.log`" -Wait"
Write-Host "   Restart:  Stop-ScheduledTask -TaskName $TaskName; Start-ScheduledTask -TaskName $TaskName"
Write-Host "   Stop:     Stop-ScheduledTask -TaskName $TaskName"
