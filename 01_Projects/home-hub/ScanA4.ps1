$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $here "ScanA4.log"
function Log($m) {
    $line = "{0:HH:mm:ss} {1}" -f (Get-Date), $m
    Add-Content -LiteralPath $log -Encoding UTF8 -Value $line
    Write-Host $line
}
function Set-Id($bag, $id, $value) {
    foreach ($p in $bag.Properties) {
        if ($p.PropertyID -ne $id) { continue }
        try {
            $p.Value = $value
            Log ("prop " + $id + "=" + $value)
            return $true
        } catch {
            Log ("prop " + $id + " fail " + $_.Exception.Message)
            return $false
        }
    }
    return $false
}
function Test-Empty($err) {
    $ex = $err.Exception
    if ($ex.InnerException) { $ex = $ex.InnerException }
    $msg = [string]$ex.Message
    if ($ex.HResult -eq -2145320957) { return $true }
    if ($msg -match "податчик|nothing|empty|ADF|80210003|бумаг") { return $true }
    return $false
}
function Add-Ascii($ms, [string]$s) {
    $b = [System.Text.Encoding]::ASCII.GetBytes($s)
    $ms.Write($b, 0, $b.Length)
}
function Save-JpegPdf([string]$jpegPath, [string]$pdfPath) {
    $jpeg = [System.IO.File]::ReadAllBytes($jpegPath)
    $w = 0
    $h = 0
    $comp = 0
    $limit = [Math]::Min(65536, $jpeg.Length - 10)
    for ($i = 0; $i -lt $limit; $i++) {
        if ($jpeg[$i] -ne 255) { continue }
        $m = $jpeg[$i + 1]
        if ($m -ne 0xC0 -and $m -ne 0xC2) { continue }
        $h = ([int]$jpeg[$i + 5] -shl 8) -bor [int]$jpeg[$i + 6]
        $w = ([int]$jpeg[$i + 7] -shl 8) -bor [int]$jpeg[$i + 8]
        $comp = [int]$jpeg[$i + 9]
        break
    }
    if ($w -le 0 -or $h -le 0) { throw "jpeg size" }
    $cs = "/DeviceGray"
    if ($comp -ge 3) { $cs = "/DeviceRGB" }
    $inv = [System.Globalization.CultureInfo]::InvariantCulture
    $pw = ($w * 72.0 / 300.0).ToString("0.00", $inv)
    $ph = ($h * 72.0 / 300.0).ToString("0.00", $inv)
    $content = [System.Text.Encoding]::ASCII.GetBytes("q`n$pw 0 0 $ph 0 0 cm`n/Im0 Do`nQ`n")
    $ms = New-Object System.IO.MemoryStream
    Add-Ascii $ms "%PDF-1.4`n"
    $o1 = $ms.Position
    Add-Ascii $ms "1 0 obj`n<< /Type /Catalog /Pages 2 0 R >>`nendobj`n"
    $o2 = $ms.Position
    Add-Ascii $ms "2 0 obj`n<< /Type /Pages /Count 1 /Kids [3 0 R] >>`nendobj`n"
    $o3 = $ms.Position
    Add-Ascii $ms "3 0 obj`n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 $pw $ph] /Contents 4 0 R /Resources << /XObject << /Im0 5 0 R >> >> >>`nendobj`n"
    $o4 = $ms.Position
    Add-Ascii $ms ("4 0 obj`n<< /Length " + $content.Length + " >>`nstream`n")
    $ms.Write($content, 0, $content.Length)
    Add-Ascii $ms "endstream`nendobj`n"
    $o5 = $ms.Position
    Add-Ascii $ms ("5 0 obj`n<< /Type /XObject /Subtype /Image /Width " + $w + " /Height " + $h + " /ColorSpace " + $cs + " /BitsPerComponent 8 /Filter /DCTDecode /Length " + $jpeg.Length + " >>`nstream`n")
    $ms.Write($jpeg, 0, $jpeg.Length)
    Add-Ascii $ms "`nendstream`nendobj`n"
    $xref = $ms.Position
    Add-Ascii $ms "xref`n0 6`n"
    Add-Ascii $ms "0000000000 65535 f `n"
    foreach ($off in @($o1, $o2, $o3, $o4, $o5)) {
        Add-Ascii $ms ("{0:D10} 00000 n `n" -f ([int64]$off))
    }
    Add-Ascii $ms ("trailer`n<< /Size 6 /Root 1 0 R >>`nstartxref`n" + $xref + "`n%%EOF`n")
    if (Test-Path -LiteralPath $pdfPath) { Remove-Item -LiteralPath $pdfPath -Force }
    [System.IO.File]::WriteAllBytes($pdfPath, $ms.ToArray())
}
function Set-Page($item) {
    foreach ($p in $item.Properties) {
        try {
            if ($p.Name -eq "Horizontal Resolution" -or $p.Name -eq "Vertical Resolution") { $p.Value = 300 }
        } catch { Log ($p.Name + " " + $_.Exception.Message) }
    }
    foreach ($p in $item.Properties) {
        try {
            if ($p.Name -eq "Horizontal Start Position" -or $p.Name -eq "Vertical Start Position") { $p.Value = 0 }
            if ($p.Name -eq "Horizontal Extent" -or $p.Name -eq "Vertical Extent") {
                $max = [int]$p.SubTypeMax
                $want = $(if ($p.Name -eq "Horizontal Extent") { 2480 } else { 3508 })
                if ($want -gt $max) { $want = $max }
                $p.Value = $want
                if (-not $script:extentsLogged) {
                    Log ($p.Name + "=" + $want + " max=" + $max)
                }
            }
        } catch { Log ($p.Name + " " + $_.Exception.Message) }
    }
    $script:extentsLogged = $true
}
Remove-Item -LiteralPath $log -ErrorAction SilentlyContinue
Log "start"
try {
    $dm = New-Object -ComObject WIA.DeviceManager
    $usb = $null
    $other = $null
    foreach ($info in $dm.DeviceInfos) {
        if ($info.Type -ne 1) { continue }
        $name = ""
        foreach ($p in $info.Properties) { if ($p.Name -eq "Name") { $name = [string]$p.Value } }
        Log ("device type=1 name=" + $name)
        if ($name -eq "HP LJ M521 Scan") { $usb = $info }
        elseif ($null -eq $other) { $other = $info }
    }
    $chosen = $usb
    if ($null -eq $chosen) { $chosen = $other }
    if ($null -eq $chosen) { throw "scanner not found" }
    $device = $chosen.Connect()
    Log "connected"
    if (-not (Set-Id $device 3088 33)) { Set-Id $device 3088 1 | Out-Null }
    $hub = "D:\Hub\Inbox\сканы"
    $desk = Join-Path $env:USERPROFILE "OneDrive\Desktop\Сканы"
    if (Test-Path -LiteralPath "D:\Hub\Inbox") {
        if (-not (Test-Path -LiteralPath $hub)) { New-Item -ItemType Directory -Force -Path $hub | Out-Null }
        $dir = $hub
    } else {
        if (-not (Test-Path -LiteralPath $desk)) { New-Item -ItemType Directory -Force -Path $desk | Out-Null }
        $dir = $desk
    }
    Log ("dir " + $dir)
    $stamp = "{0:yyyyMMdd_HHmmss}" -f (Get-Date)
    $jpeg = "{B96B3CAE-0728-11D3-9D7B-0000F81EF32E}"
    $script:extentsLogged = $false
    $n = 0
    while ($true) {
        $item = $null
        foreach ($it in $device.Items) { $item = $it; break }
        if ($null -eq $item) { throw "no scan item" }
        Set-Page $item
        try {
            $image = $item.Transfer($jpeg)
        } catch {
            if ((Test-Empty $_) -and $n -gt 0) {
                Log ("готово " + $n)
                exit 0
            }
            throw
        }
        $n++
        $tmp = Join-Path $here "page.jpg"
        if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force }
        $image.SaveFile($tmp)
        $path = Join-Path $dir ("ScanA4_{0}_{1:D2}.pdf" -f $stamp, $n)
        Save-JpegPdf $tmp $path
        Remove-Item -LiteralPath $tmp -Force
        Log ("saved " + $path)
    }
} catch {
    $msg = $_.Exception.Message
    Log ("ERROR " + $msg)
    if ($msg -match "податчик|nothing|empty|ADF|80210003|бумаг") {
        Log "Положите листы в автоподатчик и запустите ещё раз."
    }
    exit 1
}
