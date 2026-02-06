Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

param(
  [switch]$Installed,
  [string]$ArtifactRoot = '',
  [string]$LogFile = '',
  [string]$TranscriptFile = ''
)

function Add-LogLine {
  param([string]$Line)
  Add-Content -Path $LogFile -Value $Line
}

function Add-TranscriptLine {
  param([string]$Line)
  if ($TranscriptFile) {
    Add-Content -Path $TranscriptFile -Value $Line
  }
}

function Invoke-OctopusInNewShell {
  param([string]$Arguments)
  $command = "`$ErrorActionPreference='Stop'; octopusos $Arguments"
  Write-Host "powershell -NoProfile -Command \"octopusos $Arguments\""
  Add-LogLine "`n$ powershell -NoProfile -Command \"octopusos $Arguments\""
  Add-TranscriptLine "`n$ powershell -NoProfile -Command \"octopusos $Arguments\""
  $output = & powershell.exe -NoProfile -Command $command 2>&1
  $exitCode = $LASTEXITCODE
  $text = ($output | Out-String).TrimEnd()
  if ($text) {
    Add-LogLine $text
    Add-TranscriptLine $text
  }
  if ($exitCode -ne 0) {
    throw "octopusos $Arguments failed with exit code $exitCode"
  }
  return $text
}

function Parse-DoctorValue {
  param(
    [string]$DoctorOutput,
    [string]$Label
  )
  $m = [regex]::Match($DoctorOutput, "(?m)$([regex]::Escape($Label))\s*:\s*(.+)$")
  if ($m.Success) {
    return $m.Groups[1].Value.Trim()
  }
  return ''
}

function Parse-PortFromConfig {
  param([string]$ConfigOutput)
  $m = [regex]::Match($ConfigOutput, '(?m)Port\s*\|\s*(\d+)')
  if ($m.Success) {
    return [int]$m.Groups[1].Value
  }
  return 8080
}

function Parse-StatusField {
  param(
    [string]$StatusOutput,
    [string]$Field
  )
  $m = [regex]::Match($StatusOutput, "(?m)$([regex]::Escape($Field))\s*\|\s*(.+)$")
  if ($m.Success) {
    return $m.Groups[1].Value.Trim()
  }
  return ''
}

function Parse-Url {
  param([string]$StatusOutput)
  $m = [regex]::Match($StatusOutput, '(?m)URL\s*\|\s*(http://[^\s|]+)')
  if ($m.Success) {
    return $m.Groups[1].Value.Trim()
  }
  return ''
}

function Write-Diagnostics {
  Write-Host '[DIAG] collecting doctor and runtime logs'
  try {
    $doctor = Invoke-OctopusInNewShell -Arguments 'doctor'
    Add-LogLine "`n[DIAG] doctor output"
    Add-LogLine $doctor

    $logPath = Parse-DoctorValue -DoctorOutput $doctor -Label 'Log file'
    if ($logPath -and (Test-Path $logPath)) {
      Add-LogLine "`n[DIAG] log tail from $logPath"
      Get-Content -Path $logPath -Tail 80 | ForEach-Object { Add-LogLine $_ }
    }
  } catch {
    Add-LogLine "[DIAG] unable to collect diagnostics: $($_.Exception.Message)"
  }
}

function Invoke-Check {
  param(
    [string]$Name,
    [scriptblock]$Action
  )
  try {
    Add-TranscriptLine "[STEP] $Name"
    & $Action
    Write-Host "[PASS] $Name"
    Add-TranscriptLine "[PASS] $Name"
  } catch {
    Write-Host "[FAIL] $Name: $($_.Exception.Message)"
    Add-TranscriptLine "[FAIL] $Name: $($_.Exception.Message)"
    Write-Diagnostics
    throw
  }
}

if (-not $ArtifactRoot) {
  $ArtifactRoot = Join-Path $PSScriptRoot '..\..\..\publish\artifacts'
}

if (-not $LogFile) {
  $LogFile = Join-Path $PSScriptRoot 'smoke-result.log'
}

if (-not $TranscriptFile) {
  $TranscriptFile = Join-Path (Split-Path $LogFile -Parent) 'smoke_transcript.txt'
}

New-Item -ItemType Directory -Force -Path (Split-Path $LogFile -Parent), (Split-Path $TranscriptFile -Parent) | Out-Null

"Smoke started: $(Get-Date -Format s)" | Set-Content -Path $LogFile -Encoding UTF8
"Smoke started: $(Get-Date -Format s)" | Set-Content -Path $TranscriptFile -Encoding UTF8

Invoke-Check -Name 'octopusos command available in new PowerShell' -Action {
  Write-Host 'powershell -NoProfile -Command "Get-Command octopusos"'
  Add-TranscriptLine '$ powershell -NoProfile -Command "Get-Command octopusos"'
  $output = & powershell.exe -NoProfile -Command "Get-Command octopusos | Out-String" 2>&1
  if ($LASTEXITCODE -ne 0) {
    throw 'Get-Command octopusos failed in new shell'
  }
  $text = ($output | Out-String).TrimEnd()
  Add-LogLine $text
  Add-TranscriptLine $text
}

Invoke-Check -Name 'octopusos --version' -Action {
  $v = Invoke-OctopusInNewShell -Arguments '--version'
  if (-not $v) { throw 'empty version output' }
}

$doctorOutput = ''
Invoke-Check -Name 'doctor outputs runtime paths' -Action {
  $doctorOutput = Invoke-OctopusInNewShell -Arguments 'doctor'
  if ($doctorOutput -notmatch 'Data dir') { throw 'doctor output missing Data dir' }
  if ($doctorOutput -notmatch 'Log file') { throw 'doctor output missing Log file' }
  if ($doctorOutput -notmatch 'Status file') { throw 'doctor output missing Status file' }
}

Invoke-Check -Name 'webui start' -Action {
  $out = Invoke-OctopusInNewShell -Arguments 'webui start'
  if (-not $out) { throw 'start output empty' }
}

$statusOutput = ''
Invoke-Check -Name 'webui status running' -Action {
  $statusOutput = Invoke-OctopusInNewShell -Arguments 'webui status'
  if ($statusOutput -notmatch '(?i)Running\s*\|\s*yes') { throw 'status does not indicate running' }
  if ($statusOutput -notmatch 'http://') { throw 'status missing URL' }
}

Invoke-Check -Name 'webui start idempotent' -Action {
  $s2 = Invoke-OctopusInNewShell -Arguments 'webui start'
  if ($s2 -notmatch 'already running') { throw 'idempotent message missing' }
}

Invoke-Check -Name 'logs tail' -Action {
  $l = Invoke-OctopusInNewShell -Arguments 'logs --tail --lines 5'
  # Allow empty logs, but command must complete successfully.
  Add-LogLine "logs_tail_length=$($l.Length)"
}

Invoke-Check -Name 'port conflict fallback' -Action {
  $null = Invoke-OctopusInNewShell -Arguments 'webui stop'
  Start-Sleep -Seconds 1

  $configOutput = Invoke-OctopusInNewShell -Arguments 'webui config --show'
  $preferredPort = Parse-PortFromConfig -ConfigOutput $configOutput

  $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $preferredPort)
  try {
    $listener.Start()
    Add-LogLine "blocked_port=$preferredPort"
    Add-TranscriptLine "blocked_port=$preferredPort"

    $startOut = Invoke-OctopusInNewShell -Arguments 'webui start'
    $statusAfter = Invoke-OctopusInNewShell -Arguments 'webui status'

    if ($statusAfter -notmatch '(?i)Running\s*\|\s*yes') {
      throw 'status does not indicate running after fallback start'
    }

    $url = Parse-Url -StatusOutput $statusAfter
    if (-not $url) {
      throw 'status URL missing after fallback start'
    }

    $uri = [System.Uri]$url
    $actualPort = [int]$uri.Port
    $portSource = Parse-StatusField -StatusOutput $statusAfter -Field 'Port source'

    $fallbackObserved = ($actualPort -ne $preferredPort) -or ($portSource -match '(?i)fallback') -or ($startOut -match '(?i)preferred port')
    Add-TranscriptLine "port_decision preferred=$preferredPort actual=$actualPort port_source=$portSource"
    if (-not $fallbackObserved) {
      throw "fallback was not observed (preferred=$preferredPort actual=$actualPort port_source='$portSource')"
    }
  } finally {
    $listener.Stop()
  }
}

Invoke-Check -Name 'control API status reachable with token' -Action {
  if (-not $doctorOutput) {
    $doctorOutput = Invoke-OctopusInNewShell -Arguments 'doctor'
  }
  $tokenPath = Parse-DoctorValue -DoctorOutput $doctorOutput -Label 'Control token file'
  if (-not $tokenPath) {
    throw 'unable to parse control token path from doctor output'
  }
  if (-not (Test-Path $tokenPath)) {
    throw "token file not found: $tokenPath"
  }

  $token = (Get-Content -Path $tokenPath -Raw).Trim()
  if (-not $token) {
    throw 'token file is empty'
  }

  $statusNow = Invoke-OctopusInNewShell -Arguments 'webui status'
  $url = Parse-Url -StatusOutput $statusNow
  if (-not $url) {
    throw 'cannot determine daemon URL from status output'
  }

  $uri = [System.Uri]$url
  $apiUrl = "http://$($uri.Host):$($uri.Port)/api/daemon/status"
  $headers = @{ 'X-OctopusOS-Token' = $token }
  $resp = Invoke-RestMethod -Uri $apiUrl -Headers $headers -Method Get -TimeoutSec 5

  foreach ($required in @('running', 'pid', 'port', 'url')) {
    if (-not ($resp.PSObject.Properties.Name -contains $required)) {
      throw "control API response missing field: $required"
    }
  }

  if (-not [bool]$resp.running) {
    throw 'control API reported not running'
  }
}

Invoke-Check -Name 'webui stop' -Action {
  $out = Invoke-OctopusInNewShell -Arguments 'webui stop'
  if (-not $out) { throw 'stop output empty' }
}

Invoke-Check -Name 'webui status stopped' -Action {
  $s3 = Invoke-OctopusInNewShell -Arguments 'webui status'
  if ($s3 -notmatch '(?i)Running\s*\|\s*no') { throw 'status does not indicate stopped' }
}

Write-Host "Smoke complete. Log: $LogFile"
Add-TranscriptLine "Smoke complete. Log: $LogFile"
