<#
    Copies VS Code user settings and keybindings into the Windows user profile.
    Existing files are backed up next to this script before overwriting.

    Usage:
        powershell -ExecutionPolicy Bypass -File .\install-settings.ps1
#>

$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $env:APPDATA 'Code\User'

if (-not (Test-Path $target)) {
    New-Item -ItemType Directory -Path $target -Force | Out-Null
    Write-Host "Created folder: $target"
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path $here "backup-$stamp"
New-Item -ItemType Directory -Path $backup -Force | Out-Null

$pairs = @(
    @{ Source = 'settings.windows.json';     Target = 'settings.json' },
    @{ Source = 'keybindings.windows.json';  Target = 'keybindings.json' }
)

foreach ($pair in $pairs) {
    $src = Join-Path $here $pair.Source
    $dst = Join-Path $target $pair.Target

    if (-not (Test-Path $src)) {
        Write-Host "SKIP (not found): $($pair.Source)" -ForegroundColor Yellow
        continue
    }

    if (Test-Path $dst) {
        Copy-Item $dst (Join-Path $backup $pair.Target) -Force
        Write-Host "Backed up: $($pair.Target)"
    }

    Copy-Item $src $dst -Force
    Write-Host "Installed: $($pair.Target) -> $dst" -ForegroundColor Green
}

Write-Host ""
Write-Host "Done. Backup of previous files: $backup"
Write-Host "Restart VS Code to apply the settings."
