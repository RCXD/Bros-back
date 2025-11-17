# ============================================
# OSRM customize background-worker quick test
# ============================================

Write-Host "[1] Setting environment variables and test artifacts..."

$env:OSRM_DATA_DIR = "$PWD\osrm-test"
New-Item -ItemType Directory -Force $env:OSRM_DATA_DIR | Out-Null
New-Item -ItemType File -Force (Join-Path $env:OSRM_DATA_DIR 'map.osrm') | Out-Null

# Speed up debounce
$env:OSRM_CUSTOMIZE_DEBOUNCE = "0.2"


# ============================================
# Create stub osrm-customize
# ============================================
Write-Host "[2] Creating stub osrm-customize..."

New-Item -ItemType Directory -Force .\scripts | Out-Null

@"
@echo off
setlocal enabledelayedexpansion
echo %date% %time% CUSTOMIZE %* >> "%OSRM_DATA_DIR%\customize.log"
exit /b 0
"@ | Set-Content .\scripts\osrm-customize.cmd


# Prepend stub folder to PATH
$env:PATH = "$PWD\scripts;" + $env:PATH


# ============================================
# Run Flask in a separate window
# ============================================
Write-Host "[3] Starting Flask WITHOUT reloader..."
Write-Host "    A new PowerShell window will open."
Write-Host "    Close it manually when done testing.`n"

$flaskCommand = @"
`$env:FLASK_APP = 'apps.app:create_app("development")'
flask run --no-reload --port 8000
"@

Start-Process powershell "-NoExit -Command $flaskCommand"


# ============================================
# Python poke helper
# ============================================
Write-Host "[4] Creating Python poke script (poke_test.py)..."

@"
from apps.app import create_app

app = create_app('development')

with app.app_context():
    from apps.route.views import schedule_osrm_customize
    schedule_osrm_customize()
    print("scheduled OSRM customize")
"@ | Set-Content .\poke_test.py


Write-Host "`n[5] Test ready!"
Write-Host "--------------------------------------------"
Write-Host "To trigger the worker manually, run:"
Write-Host "    python poke_test.py"
Write-Host ""
Write-Host "To watch customize.log:"
Write-Host "    Get-Content `"$env:OSRM_DATA_DIR\customize.log`" -Tail 20 -Wait"
Write-Host "--------------------------------------------"
