<#
    Runs both installers: settings/keybindings first, then extensions.

    Usage:
        powershell -ExecutionPolicy Bypass -File .\install-all.ps1
#>

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

& (Join-Path $here 'install-settings.ps1')
& (Join-Path $here 'install-extensions.ps1')

Write-Host ""
Write-Host "All done. Restart VS Code."
