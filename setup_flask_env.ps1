Write-Host "[1/5] 가상환경 생성 중..."
py -3.11 -m venv venv
if (!$?) {
    Write-Host "❌ 가상환경 생성 실패. Python 3.11이 설치되어 있는지 확인하세요."
    pause
    exit
}

Write-Host "[2/5] 가상환경 활성화 중..."
& .\venv\Scripts\Activate.ps1

Write-Host "[3/5] 패키지 설치 중..."
pip install --upgrade pip
pip install flask alembic flask_login flask_sqlalchemy mysql-connector-python mysql sqlalchemy email-validator flask-cors Flask-Migrate
if (!$?) {
    Write-Host "❌ 패키지 설치 실패. 네트워크 연결을 확인하세요."
    pause
    exit
}

Write-Host "[4/5] .env 파일 생성 중..."

# .env 파일 내용 정의
$envContent = @"
FLASK_DEBUG=True
SQLALCHEMY_DATABASE_URI=mysql+mysqlconnector://root:1234@localhost/brosback
"@

# 파일 생성
$envPath = ".\.env"
Set-Content -Path $envPath -Value $envContent -Encoding UTF8

Write-Host "✅ .env 파일이 생성되었습니다. (경로: $envPath)"
Write-Host "   - FLASK_DEBUG=True"
Write-Host "   - SQLALCHEMY_DATABASE_URI=mysql+mysqlconnector://root:1234@localhost/brosback"

Write-Host "[5/5] 완료!"
Write-Host "-------------------------------------------"
Write-Host "Flask 개발환경이 성공적으로 구성되었습니다."
Write-Host '가상환경 활성화: & .\venv\Scripts\Activate.ps1'
Write-Host "-------------------------------------------"

pause
