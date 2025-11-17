param(
    # OSM PBF 파일 경로 (필수)
    [Parameter(Mandatory = $true)]
    [string]$PbfPath,

    # OSRM 프로필(lua) 파일 경로 (기본: car.lua)
    [string]$ProfilePath = "C:\osrm\profiles\car.lua",

    # 출력 디렉토리 (OSRM_DATA_DIR, 기본: C:\osrm)
    [string]$OutDir = "C:\osrm"
)

Write-Host "============================================"
Write-Host " OSRM Preprocessing Pipeline"
Write-Host "============================================"
Write-Host "[1] PBF       :" $PbfPath
Write-Host "[1] Profile   :" $ProfilePath
Write-Host "[1] Output dir:" $OutDir
Write-Host "============================================"

# 0) 경로 정리
$PbfPath   = (Resolve-Path $PbfPath).Path
$ProfilePath = (Resolve-Path $ProfilePath).Path
New-Item -ItemType Directory -Force $OutDir | Out-Null
Set-Location $OutDir

# 1) osrm-extract
Write-Host ""
Write-Host "[2] Running osrm-extract..."
Write-Host "    osrm-extract -p $ProfilePath $PbfPath"
Write-Host ""

$extract = Start-Process `
    -FilePath "osrm-extract" `
    -ArgumentList @("-p", $ProfilePath, $PbfPath) `
    -NoNewWindow `
    -PassThru `
    -Wait

if ($extract.ExitCode -ne 0) {
    Write-Host "[2] ERROR: osrm-extract failed with code" $extract.ExitCode -ForegroundColor Red
    exit 1
}

# 2) osrm-partition
Write-Host ""
Write-Host "[3] Running osrm-partition..."
Write-Host "    osrm-partition map.osrm"
Write-Host ""

$partition = Start-Process `
    -FilePath "osrm-partition" `
    -ArgumentList @("map.osrm") `
    -NoNewWindow `
    -PassThru `
    -Wait

if ($partition.ExitCode -ne 0) {
    Write-Host "[3] ERROR: osrm-partition failed with code" $partition.ExitCode -ForegroundColor Red
    exit 1
}

# 3) osrm-customize
Write-Host ""
Write-Host "[4] Running osrm-customize..."
Write-Host "    osrm-customize map.osrm"
Write-Host ""

$customize = Start-Process `
    -FilePath "osrm-customize" `
    -ArgumentList @("map.osrm") `
    -NoNewWindow `
    -PassThru `
    -Wait

if ($customize.ExitCode -ne 0) {
    Write-Host "[4] ERROR: osrm-customize failed with code" $customize.ExitCode -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "============================================"
Write-Host " Done."
Write-Host " Generated files in $OutDir :"
Get-ChildItem $OutDir map.osrm*
Write-Host "============================================"
