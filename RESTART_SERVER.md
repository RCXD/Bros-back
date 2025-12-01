# Flask Server Restart Guide

## Why Restart?

The `/route/analyze` endpoint was recently added to `apps/route/views.py`. For the Flask server to recognize new endpoints, it must be restarted.

## How to Restart

### Step 1: Find the Running Server

The Flask server is running in a terminal with this command:
```
python apps/app.py
```

### Step 2: Stop the Server

In the terminal running the server:
1. Press `Ctrl+C` to stop the Flask server
2. Wait for the server to shut down cleanly

### Step 3: Restart the Server

Run the server again:
```powershell
python apps/app.py --local
```

Or if you're not in the activated virtual environment:
```powershell
& C:\Users\M\Bros-back-clone2\venv\Scripts\Activate.ps1
python apps/app.py --local
```

### Step 4: Verify the Endpoint

Run the verification script:
```powershell
python verify_route_analyze.py
```

You should see:
```
✅ ENDPOINT EXISTS (Status: 401)
The /route/analyze endpoint is available!
```

### Step 5: Run Tests

Once verified, run the full test suite:
```powershell
python apps/test/functional/test_route_analysis.py
```

## Troubleshooting

### Server Won't Stop

If `Ctrl+C` doesn't work, find and kill the process:
```powershell
# Find Python processes
Get-Process | Where-Object {$_.ProcessName -like "*python*"}

# Kill specific process (replace PID)
Stop-Process -Id <PID> -Force
```

### Port Already in Use

If port 8002 is occupied:
```powershell
# Find what's using port 8002
netstat -ano | findstr :8002

# Kill the process (replace PID)
Stop-Process -Id <PID> -Force
```

### Wrong Environment

Make sure you're using `.env.local`:
```powershell
cat .env.local | Select-String "FLASK_PORT"
# Should show: FLASK_PORT=8002
```

## Quick Command Reference

```powershell
# Activate venv
& C:\Users\M\Bros-back-clone2\venv\Scripts\Activate.ps1

# Start server
python apps/app.py --local

# Verify endpoint
python verify_route_analyze.py

# Run tests
python apps/test/functional/test_route_analysis.py
```
