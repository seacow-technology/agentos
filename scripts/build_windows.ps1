Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

param(
  [string]$Version,
  [string]$Channel = 'stable',
  [string]$RuntimeDir = '',
  [switch]$SkipSmoke
)

$script = Join-Path $PSScriptRoot '..\windows\installer\build.ps1'
& $script -Version $Version -Channel $Channel -RuntimeDir $RuntimeDir -SkipSmoke:$SkipSmoke
