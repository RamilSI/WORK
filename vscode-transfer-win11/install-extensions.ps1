<#
    Installs all VS Code extensions listed in extensions.txt.

    Usage:
        powershell -ExecutionPolicy Bypass -File .\install-extensions.ps1
        powershell -ExecutionPolicy Bypass -File .\install-extensions.ps1 -PinVersions

    -PinVersions installs the exact versions from the source machine (may fail
    for versions that are no longer available). Without the switch the latest
    compatible versions are installed.
#>

param(
    [switch]$PinVersions
)

$ErrorActionPreference = 'Continue'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$list = Join-Path $here 'extensions.txt'

if (-not (Test-Path $list)) {
    Write-Host "ERROR: extensions.txt not found next to this script." -ForegroundColor Red
    exit 1
}

if (-not (Get-Command code -ErrorAction SilentlyContinue)) {
    Write-Host 'ERROR: VS Code CLI "code" was not found in PATH.' -ForegroundColor Red
    Write-Host 'Fix: open VS Code, press Ctrl+Shift+P, run "Shell Command: Install code command in PATH", then re-run this script.'
    exit 1
}

$failed = New-Object System.Collections.Generic.List[string]
$total = 0

Get-Content $list | Where-Object { $_.Trim() -ne '' } | ForEach-Object {
    $total++
    $spec = $_.Trim()

    if ($PinVersions) {
        $id = $spec
    }
    else {
        $id = ($spec -split '@')[0]
    }

    Write-Host ("[{0}] {1}" -f $total, $id)

    & code --install-extension $id --force 2>&1 | Out-Null

    if ($LASTEXITCODE -ne 0) {
        $failed.Add($id)
        Write-Host "    FAILED" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host ("Installed: {0} / {1}" -f ($total - $failed.Count), $total)

if ($failed.Count -gt 0) {
    $failedFile = Join-Path $here 'extensions-failed.txt'
    $failed | Set-Content -Path $failedFile -Encoding UTF8
    Write-Host "Failed extensions were written to: $failedFile" -ForegroundColor Yellow
    $failed | ForEach-Object { Write-Host "  $_" }
}
