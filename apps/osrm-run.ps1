param(
    [string]$OsrmDir = "C:\osrm",
    [int]$Port = 5000
)

$OsrmDir = (Resolve-Path $OsrmDir).Path
Set-Location $OsrmDir

Write-Host "============================================"
Write-Host " OSRM Routed Server"
Write-Host "============================================"
Write-Host "[*] OSRM dir:" $OsrmDir
Write-Host "[*] Port    :" $Port
Write-Host "============================================"
Write-Host "Command:"
Write-Host "  osrm-routed --algorithm mld map.osrm -p $Port"
Write-Host "============================================"

Start-Process `
    -FilePath "osrm-routed" `
    -ArgumentList @("--algorithm", "mld", "map.osrm", "-p", $Port) `
    -NoNewWindow
