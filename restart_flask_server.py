"""
Automatic Flask Server Restart Helper

This script helps restart the Flask server to activate the new /route/analyze endpoint.

Usage:
    python restart_flask_server.py

What it does:
    1. Finds running Flask processes on port 8002
    2. Asks for confirmation before stopping
    3. Stops the old server
    4. Starts a new server instance
    5. Verifies the endpoint is available
"""

import subprocess
import time
import sys
import os


def find_flask_processes():
    """Find Python processes that might be running Flask on port 8002"""
    try:
        # Find processes listening on port 8002
        result = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=5
        )

        pids = []
        for line in result.stdout.split("\n"):
            if ":8002" in line and "LISTENING" in line:
                # Extract PID from the end of the line
                parts = line.split()
                if parts:
                    try:
                        pid = int(parts[-1])
                        pids.append(pid)
                    except ValueError:
                        pass

        return list(set(pids))  # Remove duplicates
    except Exception as e:
        print(f"Error finding processes: {e}")
        return []


def stop_process(pid):
    """Stop a process by PID"""
    try:
        subprocess.run(
            ["taskkill", "/F", "/PID", str(pid)], capture_output=True, timeout=5
        )
        return True
    except Exception as e:
        print(f"Error stopping process {pid}: {e}")
        return False


def start_flask_server():
    """Start the Flask server"""
    print("\nStarting Flask server...")

    # Check if venv exists
    venv_python = r"C:\Users\M\Bros-back-clone2\venv\Scripts\python.exe"
    if not os.path.exists(venv_python):
        print(f"ERROR: Virtual environment not found at {venv_python}")
        return False

    # Start server in a new terminal window
    try:
        subprocess.Popen(
            [
                "powershell.exe",
                "-Command",
                f"cd C:\\Users\\M\\Bros-back-clone2; & '{venv_python}' apps/app.py --local",
            ],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        print("✅ Flask server started in new terminal window")
        print("   Waiting 5 seconds for server to initialize...")
        time.sleep(5)
        return True
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        return False


def verify_endpoint():
    """Verify the endpoint is available"""
    print("\nVerifying endpoint...")

    try:
        result = subprocess.run(
            [sys.executable, "verify_route_analyze.py"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        print(result.stdout)
        return result.returncode == 0
    except Exception as e:
        print(f"Error verifying endpoint: {e}")
        return False


def main():
    print("=" * 70)
    print("Flask Server Restart Helper")
    print("=" * 70)

    # Find running processes
    print("\n1. Finding running Flask processes on port 8002...")
    pids = find_flask_processes()

    if pids:
        print(f"   Found {len(pids)} process(es): {pids}")

        # Ask for confirmation
        response = input("\n   Stop these processes? (y/N): ").strip().lower()
        if response != "y":
            print("   Cancelled by user")
            return

        # Stop processes
        print("\n2. Stopping old Flask processes...")
        for pid in pids:
            if stop_process(pid):
                print(f"   ✅ Stopped process {pid}")
            else:
                print(f"   ❌ Failed to stop process {pid}")

        time.sleep(2)
    else:
        print("   No Flask processes found on port 8002")

    # Start new server
    print("\n3. Starting new Flask server...")
    if not start_flask_server():
        print("\n❌ Failed to start server")
        print("\nManual restart required:")
        print("   1. Open a terminal")
        print("   2. Run: python apps/app.py --local")
        return

    # Verify endpoint
    print("\n4. Verifying /route/analyze endpoint...")
    if verify_endpoint():
        print("\n" + "=" * 70)
        print("✅ SUCCESS - Server restarted and endpoint is active!")
        print("=" * 70)
        print("\nYou can now run tests:")
        print("   python apps/test/functional/test_route_analysis.py")
    else:
        print("\n" + "=" * 70)
        print("⚠️  Server started but endpoint verification failed")
        print("=" * 70)
        print("\nPlease check:")
        print("   1. Server terminal window for errors")
        print("   2. Run verify_route_analyze.py again in a few seconds")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback

        traceback.print_exc()
