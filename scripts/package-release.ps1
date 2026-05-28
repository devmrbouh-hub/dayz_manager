# Package Windows release ZIP for GitHub Releases.
# Prereqs: dist\DayZManager.exe (build.bat), bercon-cli.exe in repo root.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Version = "1.0.0"
if ($env:RELEASE_VERSION) { $Version = $env:RELEASE_VERSION.TrimStart("v") }

$Exe = Join-Path $Root "dist\DayZManager.exe"
$Bercon = Join-Path $Root "bercon-cli.exe"
$Template = Join-Path $Root "config\config-host-template.json"

foreach ($p in @($Exe, $Bercon, $Template)) {
    if (-not (Test-Path $p)) {
        Write-Error "Missing: $p"
    }
}

$OutDir = Join-Path $Root "dist\release"
$Stage = Join-Path $OutDir "dayz_manager-v$Version-windows-x64"
$ZipName = "dayz_manager-v$Version-windows-x64.zip"
$ZipPath = Join-Path $OutDir $ZipName

if (Test-Path $Stage) { Remove-Item $Stage -Recurse -Force }
New-Item -ItemType Directory -Path (Join-Path $Stage "config") -Force | Out-Null

Copy-Item $Exe (Join-Path $Stage "DayZManager.exe")
Copy-Item $Bercon (Join-Path $Stage "bercon-cli.exe")
Copy-Item $Template (Join-Path $Stage "config\config-host-template.json")

@(
"DayZ Server Manager v$Version (Windows x64)"
""
"1. copy config\config-host-template.json -> config\config.json"
"2. Edit config\config.json (api_key, paths, ports, RCON)"
"3. Run DayZManager.exe"
"4. Open http://127.0.0.1:8000"
""
"Docs: https://github.com/devmrbouh-hub/dayz_manager"
) | Set-Content -Path (Join-Path $Stage "README-RELEASE.txt") -Encoding UTF8

if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Compress-Archive -Path $Stage -DestinationPath $ZipPath -Force

Write-Host "Created: $ZipPath"
Write-Host "Upload to: https://github.com/devmrbouh-hub/dayz_manager/releases/new"
