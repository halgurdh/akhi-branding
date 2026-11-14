# Copyright (c) 2026 the AkhiBrowser authors. All rights reserved.
# Sets up this PC as the self-hosted runner of akhi-branding's Release workflow, once:
#   powershell -ExecutionPolicy Bypass -File browser/branding/akhi/tools/setup_runner.ps1
# The runner starts at logon as the current user (so it reaches G: and the keys) and needs gh signed in.
param(
  [string]$Dir = "C:\actions-runner-akhi",
  [string]$Version = "2.338.2",
  [string]$Sha256 = "a1f17aa987fc8158bc7521d284912267a0d01b7c2c4684b33c86783b5e8221cc"
)
$ErrorActionPreference = "Stop"
$repo = "halgurdh/akhi-branding"
New-Item -ItemType Directory -Force $Dir | Out-Null
Set-Location $Dir
if (-not (Test-Path "$Dir\config.cmd")) {
  $zip = "$Dir\runner.zip"
  Invoke-WebRequest "https://github.com/actions/runner/releases/download/v$Version/actions-runner-win-x64-$Version.zip" -OutFile $zip
  if ((Get-FileHash $zip -Algorithm SHA256).Hash.ToLower() -ne $Sha256) { throw "The runner download's checksum is wrong" }
  Expand-Archive $zip -DestinationPath $Dir -Force
  Remove-Item $zip
}
if (-not (Test-Path "$Dir\.runner")) {
  $token = gh api -X POST "repos/$repo/actions/runners/registration-token" --jq .token
  & "$Dir\config.cmd" --unattended --url "https://github.com/$repo" --token $token --name "$env:COMPUTERNAME-akhi" `
    --labels "akhi-release" --work "_work" --replace
}
$action = New-ScheduledTaskAction -Execute "$Dir\run.cmd" -WorkingDirectory $Dir
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "AkhiBrowser release runner" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName "AkhiBrowser release runner"
Write-Output "The runner is set up and started; it starts again at every logon."
