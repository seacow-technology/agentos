Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

param(
  [string]$Version,
  [string]$Channel = 'stable',
  [string]$OutRoot = '',
  [string]$RuntimeDir = '',
  [switch]$SkipSmoke
)

function Get-ProjectVersion {
  param([string]$ProjectRoot)
  $pyproject = Join-Path $ProjectRoot 'pyproject.toml'
  if (-not (Test-Path $pyproject)) {
    throw "pyproject.toml not found: $pyproject"
  }
  $content = Get-Content $pyproject -Raw
  $m = [regex]::Match($content, '(?m)^version\s*=\s*"([^"]+)"')
  if (-not $m.Success) {
    throw 'Unable to parse version from pyproject.toml'
  }
  return $m.Groups[1].Value
}

function Get-MsiVersion {
  param([string]$RawVersion)
  # MSI version must be strictly numeric MAJOR.MINOR.PATCH.
  $m = [regex]::Match($RawVersion, '^(\d+)\.(\d+)\.(\d+)')
  if (-not $m.Success) {
    throw "Version '$RawVersion' cannot be converted to MSI version. Expected prefix x.y.z"
  }
  return "$($m.Groups[1].Value).$($m.Groups[2].Value).$($m.Groups[3].Value)"
}

function Ensure-WixToolset {
  $wixCmd = Get-Command wix -ErrorAction SilentlyContinue
  if (-not $wixCmd) {
    Write-Host 'Installing WiX Toolset v4...'
    dotnet tool install --global wix --version 4.* | Out-Host
    $env:PATH = "$env:PATH;$env:USERPROFILE\\.dotnet\\tools"
  }

  wix --version | Out-Host
  wix extension add WixToolset.Util.wixext | Out-Host
  wix extension add WixToolset.Heat.wixext | Out-Host
}

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..\..')
if (-not $Version) {
  $Version = Get-ProjectVersion -ProjectRoot $RepoRoot
}
$MsiVersion = Get-MsiVersion -RawVersion $Version

if (-not $OutRoot) {
  $OutRoot = Join-Path $RepoRoot "publish\artifacts\$Version\windows"
}

if (-not $RuntimeDir) {
  $RuntimeDir = Join-Path $PSScriptRoot 'payload'
}

if (-not (Test-Path $RuntimeDir)) {
  throw "Runtime directory not found: $RuntimeDir"
}

$runtimeExe = Join-Path $RuntimeDir 'octopusos.exe'
if (-not (Test-Path $runtimeExe)) {
  throw "Required runtime executable missing: $runtimeExe"
}

$ManifestDir = Join-Path $OutRoot 'manifests'
$LogsDir = Join-Path $OutRoot 'logs'
$MsiName = "octopusos-installer-$Version-windows-x86_64-$Channel.msi"
$MsiPath = Join-Path $OutRoot $MsiName
$ChecksumPath = Join-Path $OutRoot 'checksums.sha256'

New-Item -ItemType Directory -Force -Path $OutRoot, $ManifestDir, $LogsDir | Out-Null

Ensure-WixToolset

$productWxs = Join-Path $PSScriptRoot 'wix\Product.wxs'
$harvestWxs = Join-Path $PSScriptRoot 'wix\harvest.wxs'

Write-Host "octopusos_version=$Version"
Write-Host "msi_version=$MsiVersion"
Write-Host "channel=$Channel"

wix heat dir $RuntimeDir `
  -dr INSTALLFOLDER `
  -cg RuntimeFiles `
  -var var.RuntimeDir `
  -gg `
  -sfrag `
  -out $harvestWxs | Out-Host

if (-not (Test-Path $harvestWxs)) {
  throw "Harvest output not found: $harvestWxs"
}

$harvestCount = (Select-String -Path $harvestWxs -Pattern '<File\s' -AllMatches).Matches.Count
Write-Host "Harvest output file path: $harvestWxs"
Write-Host "Harvested file count: $harvestCount"

wix build $productWxs $harvestWxs `
  -ext WixToolset.Util.wixext `
  -arch x64 `
  -culture en-us `
  -d Version=$MsiVersion `
  -d FullVersion=$Version `
  -d Channel=$Channel `
  -d RuntimeDir=$RuntimeDir `
  -o $MsiPath | Out-Host

$manifest = @{
  name = $MsiName
  full_version = $Version
  msi_version = $MsiVersion
  channel = $Channel
  generated_at = (Get-Date).ToString('s')
  artifact_root = $OutRoot
  runtime_dir = $RuntimeDir
  msi_path = $MsiPath
  harvest_output = $harvestWxs
  harvested_file_count = $harvestCount
  expected_commands = @(
    'octopusos --version',
    'octopusos doctor',
    'octopusos webui start',
    'octopusos webui status',
    'octopusos logs --tail --lines 5',
    'octopusos webui stop'
  )
}
$manifestJson = $manifest | ConvertTo-Json -Depth 8
$manifestJson | Set-Content -Path (Join-Path $ManifestDir 'manifest.json') -Encoding UTF8
$manifestJson | Set-Content -Path (Join-Path $OutRoot 'manifest.json') -Encoding UTF8

$sha = (Get-FileHash -Algorithm SHA256 -Path $MsiPath).Hash.ToLowerInvariant()
"$sha *$MsiName" | Set-Content -Path $ChecksumPath -Encoding UTF8

if (-not $SkipSmoke) {
  & (Join-Path $PSScriptRoot 'smoke.ps1') -Installed -LogFile (Join-Path $LogsDir 'smoke-installed.log')
}

Write-Host "Windows installer build complete: $MsiPath"
