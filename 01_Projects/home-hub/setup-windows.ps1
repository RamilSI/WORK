#Requires -RunAsAdministrator
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path "D:\Hub" | Out-Null
Start-Transcript -Path "D:\Hub\setup.log" -Append | Out-Null

function Write-Step($Message) {
    Write-Host ""
    Write-Host "== $Message"
}

function Install-WingetPackage($Id) {
    winget install --id $Id -e --accept-package-agreements --accept-source-agreements --disable-interactivity
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne -1978335189) {
        throw "winget не смог поставить $Id (код $LASTEXITCODE)"
    }
}

Write-Step "Папки на D:"
if (-not (Test-Path "D:\")) {
    throw "Диска D: нет. Общая папка по плану должна быть на D:\Hub."
}
New-Item -ItemType Directory -Force -Path "D:\Hub\Inbox", "D:\Hub\Photos\Phone" | Out-Null

Write-Step "От сети компьютер не засыпает, экран можно гасить"
powercfg /change standby-timeout-ac 0 | Out-Null
powercfg /change hibernate-timeout-ac 0 | Out-Null
powercfg /change monitor-timeout-ac 10 | Out-Null

Write-Step "Tailscale"
if (Get-Command winget -ErrorAction SilentlyContinue) {
    Install-WingetPackage "Tailscale.Tailscale"
} else {
    $msi = Join-Path $env:TEMP "tailscale-setup-1.104.7-amd64.msi"
    Invoke-WebRequest -Uri "https://pkgs.tailscale.com/stable/tailscale-setup-1.104.7-amd64.msi" -OutFile $msi
    Start-Process msiexec.exe -ArgumentList "/i `"$msi`" /quiet /norestart" -Wait
}

Write-Step "Syncthing как служба"
$setup = Join-Path $env:TEMP "syncthing-windows-setup-v2.1.1.exe"
if (-not (Test-Path $setup)) {
    Invoke-WebRequest -Uri "https://github.com/Bill-Stewart/SyncthingWindowsSetup/releases/download/v2.1.1/syncthing-windows-setup-v2.1.1.exe" -OutFile $setup
}
$setupLog = "D:\Hub\syncthing-setup.log"
Start-Process -FilePath $setup -ArgumentList "/allusers", "/silent", "/log=`"$setupLog`"" -Wait

$exe = "C:\Program Files\Syncthing\syncthing.exe"
$home = "C:\ProgramData\Syncthing"
if (-not (Test-Path $exe)) {
    throw "Syncthing не установился: нет $exe. Смотрите $setupLog"
}

Write-Step "Права службы Syncthing на D:\Hub"
icacls "D:\Hub" /grant "SyncthingServiceAcct:(OI)(CI)M" /T | Out-Null

$deadline = (Get-Date).AddMinutes(4)
while (-not (Test-Path (Join-Path $home "config.xml")) -and (Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 2
}
if (-not (Test-Path (Join-Path $home "config.xml"))) {
    throw "Syncthing не создал $home\config.xml"
}

function Invoke-Syncthing {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$CliArgs)
    $out = Join-Path $env:TEMP "syncthing-cli-out.txt"
    $errFile = Join-Path $env:TEMP "syncthing-cli-err.txt"
    Remove-Item $out, $errFile -ErrorAction SilentlyContinue
    $proc = Start-Process -FilePath $exe -ArgumentList (@("cli", "--home", $home) + $CliArgs) -Wait -PassThru -NoNewWindow -RedirectStandardOutput $out -RedirectStandardError $errFile
    if ($proc.ExitCode -ne 0) {
        $detail = ""
        if (Test-Path $errFile) { $detail = Get-Content $errFile -Raw }
        throw "syncthing cli $($CliArgs -join ' ') код $($proc.ExitCode) $detail"
    }
    if (Test-Path $out) { return @(Get-Content $out) }
    return @()
}

$system = (Invoke-Syncthing show system) -join "`n" | ConvertFrom-Json
Invoke-Syncthing config devices $system.myID name set "DESKTOP-D6P4GIH" | Out-Null

$folders = @(Invoke-Syncthing config folders list)
if ($folders -notcontains "inbox") {
    Invoke-Syncthing config folders add --id=inbox --label=Inbox --path="D:\Hub\Inbox" --type=sendreceive | Out-Null
}
if ($folders -notcontains "phone-photos") {
    Invoke-Syncthing config folders add --id=phone-photos --label="Phone-photos" --path="D:\Hub\Photos\Phone" --type=receiveonly --ignore-delete | Out-Null
}

$macId = "BXYRRXS-A3NZQDR-VBOFNOY-DHVJOJK-5J6TLOC-MGPZUCD-GFAJ25F-7VJ44AJ"
$devices = @(Invoke-Syncthing config devices list)
if ($devices -notcontains $macId) {
    Invoke-Syncthing config devices add --device-id=$macId --name="MacBook-Pro-Ramil" --auto-accept-folders | Out-Null
}
$shared = @(Invoke-Syncthing config folders inbox devices list)
if ($shared -notcontains $macId) {
    Invoke-Syncthing config folders inbox devices add --device-id=$macId | Out-Null
}

Write-Step "KDE Connect"
$kdeInstalled = $false
if (Get-Command winget -ErrorAction SilentlyContinue) {
    winget install --id KDE.KDEConnect -e --accept-package-agreements --accept-source-agreements --disable-interactivity
    if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq -1978335189) {
        $kdeInstalled = $true
    }
}
if (-not $kdeInstalled) {
    $kde = Join-Path $env:TEMP "kdeconnect-windows.exe"
    Invoke-WebRequest -Uri "https://cdn.kde.org/ci-builds/network/kdeconnect-kde/release-26.08/windows/kdeconnect-kde-release_26.08-6961-windows-cl-msvc2022-x86_64.exe" -OutFile $kde
    Start-Process -FilePath $kde -ArgumentList "/S" -Wait
}

Write-Step "Брандмауэр: только частная сеть, без проброса на роутере"
function Ensure-Rule($Name, $Protocol, $Ports) {
    $existing = Get-NetFirewallRule -DisplayName $Name -ErrorAction SilentlyContinue
    if (-not $existing) {
        New-NetFirewallRule -DisplayName $Name -Direction Inbound -Action Allow -Protocol $Protocol -LocalPort $Ports -Profile Private | Out-Null
    } else {
        Set-NetFirewallRule -DisplayName $Name -Profile Private -Action Allow -Enabled True | Out-Null
    }
}
Ensure-Rule "Hub KDE Connect TCP" TCP "1714-1764"
Ensure-Rule "Hub KDE Connect UDP" UDP "1714-1764"
Get-NetFirewallRule -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName -like "*Syncthing*" } |
    ForEach-Object { Set-NetFirewallRule -Name $_.Name -Profile Private | Out-Null }

$publish = @'
$exe = "$env:ProgramFiles\Tailscale\tailscale.exe"
if (-not (Test-Path $exe)) { exit 0 }
$ip = & $exe ip -4 2>$null | Select-Object -First 1
if ($ip -match "^100\.") {
    Set-Content -Path "D:\Hub\Inbox\desktop-tailscale-ip.txt" -Value $ip.Trim() -Encoding ascii
}
Get-NetConnectionProfile -ErrorAction SilentlyContinue |
    Where-Object { $_.InterfaceAlias -like "Tailscale*" -and $_.NetworkCategory -ne "Private" } |
    ForEach-Object { Set-NetConnectionProfile -InterfaceAlias $_.InterfaceAlias -NetworkCategory Private }
'@
Set-Content -Path "D:\Hub\publish-tailscale-ip.ps1" -Value $publish -Encoding UTF8
try {
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File D:\Hub\publish-tailscale-ip.ps1"
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 365)
    Register-ScheduledTask -TaskName "HubTailscaleIP" -Action $action -Trigger $trigger -User "SYSTEM" -RunLevel Highest -Force | Out-Null
    Start-ScheduledTask -TaskName "HubTailscaleIP"
} catch {
    Write-Host "Задачу расписания не создал: $($_.Exception.Message)"
}

$service = Get-Service | Where-Object { $_.Name -like "*syncthing*" -or $_.DisplayName -like "*Syncthing*" } | Select-Object -First 1
if ($service) {
    Restart-Service $service.Name
}

$gui = "${env:ProgramFiles}\Tailscale\tailscale-ipn.exe"
if (Test-Path $gui) {
    Start-Process $gui
}

Write-Step "Готово"
Write-Host "Syncthing на этом компьютере: $($system.myID)"
Write-Host "Общая папка: D:\Hub\Inbox"
Write-Host "Архив фото:  D:\Hub\Photos\Phone"
Write-Host "Войдите в Tailscale в открывшемся окне тем же аккаунтом, что и на Mac."
Write-Host "Телефон: Tailscale, KDE Connect и Syncthing-Fork из Play Store."
Stop-Transcript | Out-Null
