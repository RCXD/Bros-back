param(
    [string]$PbfPath = "C:\osrm\korea-latest.osm.pbf",
    [string]$OutDir  = "C:\osrm",
    [string]$CarProfile     = "/opt/car.lua",
    [string]$HazardProfile  = "/opt/hazard_car.lua",
    [string]$ContainerImage = "osrm/osrm-backend"
)

Write-Host "============================================"
Write-Host "Docker OSRM Two-Profile Build"
Write-Host "============================================"

# 1) NORMAL PROFILE
Write-Host "=== [A] NORMAL PROFILE (car.lua) ==="
docker run --rm -t `
  -v "${PbfPath}:/data/map.pbf" `
  -v "${OutDir}:/data" `
  $ContainerImage `
  osrm-extract -p $CarProfile /data/map.pbf

docker run --rm -t `
  -v "${OutDir}:/data" `
  $ContainerImage `
  osrm-partition /data/map.osrm

docker run --rm -t `
  -v "${OutDir}:/data" `
  $ContainerImage `
  osrm-customize /data/map.osrm


# 2) HAZARD PROFILE
Write-Host "=== [B] HAZARD PROFILE (hazard_car.lua) ==="
docker run --rm -t `
  -v "${PbfPath}:/data/map.pbf" `
  -v "${OutDir}:/data" `
  -v "$OutDir/hazard_car.lua:/opt/hazard_car.lua" `
  $ContainerImage `
  osrm-extract -p $HazardProfile /data/map.pbf

# rename to map_hazard.osrm
Rename-Item "$OutDir\map.osrm" "$OutDir\map_hazard.osrm" -Force

docker run --rm -t `
  -v "${OutDir}:/data" `
  $ContainerImage `
  osrm-partition /data/map_hazard.osrm

docker run --rm -t `
  -v "${OutDir}:/data" `
  $ContainerImage `
  osrm-customize /data/map_hazard.osrm

Write-Host "============================================"
Write-Host " DONE."
Write-Host " NORMAL: map.osrm*"
Write-Host " HAZARD: map_hazard.osrm*"
Write-Host "============================================"
