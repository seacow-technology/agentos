Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

param(
  [switch]$Installed,
  [string]$ArtifactRoot = '',
  [string]$LogFile = '',
  [string]$TranscriptFile = ''
)

$script = Join-Path $PSScriptRoot '..\windows\installer\smoke.ps1'
& $script -Installed:$Installed -ArtifactRoot $ArtifactRoot -LogFile $LogFile -TranscriptFile $TranscriptFile
