import os
import subprocess
import sys
import time
import threading
from pathlib import Path

# ============================================
# 0) 프로젝트 루트
# ============================================
ROOT = Path(__file__).parent.resolve()
print("[1] Project root:", ROOT)

# ============================================
# 1) OSRM_DATA_DIR 자동 설정
# ============================================
osrm_dir = ROOT / "osrm-test"
os.environ["OSRM_DATA_DIR"] = str(osrm_dir)
os.rm_test_dir = str(osrm_dir)

print("[2] OSRM_DATA_DIR =", os.environ["OSRM_DATA_DIR"])

os.makedirs(osrm_dir, exist_ok=True)

# map.osrm 자동 생성
map_osrm = osrm_dir / "map.osrm"
map_osrm.write_text("")  # 빈 파일
print("[2] map.osrm created:", map_osrm)

# 디바운스 짧게
os.environ["OSRM_CUSTOMIZE_DEBOUNCE"] = "0.2"

# ============================================
# 2) stub osrm-customize.cmd 생성 + PATH 추가
# ============================================
scripts_dir = ROOT / "scripts"
scripts_dir.mkdir(exist_ok=True)

stub = scripts_dir / "osrm-customize.cmd"
stub.write_text(
    "@echo off\n"
    "setlocal enabledelayedexpansion\n"
    f'echo %date% %time% CUSTOMIZE %* >> "{osrm_dir}\\customize.log"\n'
    "exit /b 0\n"
)

# PATH prepend
os.environ["PATH"] = f"{scripts_dir};" + os.environ["PATH"]

print("[3] Stub created at:", stub)
print("[3] PATH updated, searching for osrm-customize...")

# where check
try:
    out = subprocess.check_output(["where", "osrm-customize"], shell=True)
    print(out.decode())
except Exception as e:
    print("WARNING: where osrm-customize failed:", e)

# ============================================
# 3) Flask 앱 실행 (서브 프로세스)
# ============================================
print("[4] Starting Flask server...")

# Windows PowerShell을 안 쓰고 Python subprocess로 직접 실행
flask_env = os.environ.copy()
flask_env["FLASK_APP"] = "apps.app:create_app('development')"
flask_env["FLASK_ENV"] = "development"

# Flask 실행 명령
flask_cmd = [
    sys.executable,
    "-m",
    "flask",
    "run",
    "--no-reload",
    "--port",
    "8000",
]

flask_proc = subprocess.Popen(
    flask_cmd,
    cwd=str(ROOT),
    env=flask_env,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)

print("[4] Flask process started (PID:", flask_proc.pid, ")")

# ============================================
# 4) Flask 기동 대기 (최대 8초)
# ============================================
print("[4] Waiting for Flask to start...")
ready = False
for _ in range(80):
    line = flask_proc.stdout.readline()
    if line:
        print("[FLASK]", line.strip())
    if "Running on" in line:
        ready = True
        break
    time.sleep(0.1)

if not ready:
    print("ERROR: Flask did not start.")
    flask_proc.kill()
    sys.exit(1)

print("[4] Flask is ready.")

# ============================================
# 5) Flask 내부에서 schedule_osrm_customize() 트리거
# ============================================
print("[5] Triggering schedule_osrm_customize() via Python...")

import apps.app
app = apps.app.create_app("development")

with app.app_context():
    from apps.route.views import schedule_osrm_customize
    ok = schedule_osrm_customize()
    print("[5] schedule_osrm_customize() ->", ok)

# ============================================
# 6) customize.log 모니터링 스레드
# ============================================
def tail_customize():
    log_path = os.path.join(os.environ["OSRM_DATA_DIR"], "customize.log")
    print(f"[6] Tail log: {log_path}")

    # 로그 파일이 생성되기까지 기다림
    for _ in range(100):
        if os.path.exists(log_path):
            break
        time.sleep(0.1)

    if not os.path.exists(log_path):
        print("[6] ERROR: customize.log not created yet.")
        return

    with open(log_path, "r") as f:
        # 기존 라인 skip
        f.seek(0, os.SEEK_END)
        print("[6] Waiting for CUSTOMIZE logs...")
        while True:
            line = f.readline()
            if line:
                print("[CUSTOMIZE]", line.strip())
            time.sleep(0.1)

t = threading.Thread(target=tail_customize, daemon=True)
t.start()

# ============================================
# 7) 유지
# ============================================
print("[7] Test running. Press CTRL+C to exit.")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nShutting down...")
    flask_proc.terminate()
