# Environment Configuration Setup Guide

## 📋 Overview

All configuration values have been moved from hardcoded values in `apps/config/common.py` to environment files. This allows you to:

- Separate development and production configurations
- Keep sensitive data out of version control
- Easily customize settings per environment

---

## 🚀 Quick Setup

### Step 1: Choose Your Environment File

**For Development:**
```powershell
# The .env.local file is already created with your current settings
# Edit it directly:
notepad .env.local
```

**For Production:**
```powershell
# Edit the production file:
notepad .env.production
```

### Step 2: Generate Secure Keys (Important!)

**For Production, generate new secure keys:**

```powershell
# Generate SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate JWT_SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy these values into your `.env.production` file.

### Step 3: Edit Database Credentials

Update these values in your env file:
```env
DB_HOST=your-database-host
DB_PORT=3306
DB_USER=your-database-user
DB_PASSWORD=your-database-password
DB_NAME=your-database-name
```

### Step 4: Configure API Keys (Optional)

If using the roadview module, add your API keys:
```env
GOOGLE_MAPS_API_KEY=your-google-api-key
KAKAO_REST_API_KEY=your-kakao-api-key
NAVER_CLIENT_ID=your-naver-client-id
NAVER_CLIENT_SECRET=your-naver-client-secret
```

---

## 📁 File Priority

The configuration loader checks files in this order:

1. `.env.local` (for development)
2. `.env.production` (for production)
3. `.env` (fallback)

**Create the appropriate file for your environment.**

---

## 🔧 Configuration Reference

### Security Settings

```env
# SECRET_KEY - Flask secret key for session encryption
SECRET_KEY=your-secret-key-here

# JWT_SECRET_KEY - JWT token signing key
JWT_SECRET_KEY=your-jwt-secret-key-here
```

**⚠️ CRITICAL**: Never use default values in production! Generate unique random strings.

### Database Settings

```env
# Database connection parameters
DB_HOST=192.168.1.79          # Database server IP/hostname
DB_PORT=3306                   # MySQL port (default 3306)
DB_USER=user1                  # Database username
DB_PASSWORD=1234               # Database password
DB_NAME=404found_test1         # Database name

# SQLAlchemy settings
SQLALCHEMY_ECHO=True           # Log SQL queries (True/False)
SQLALCHEMY_TRACK_MODIFICATIONS=False  # Track object changes (True/False)
```

### CORS Settings

```env
# Development (allow all origins)
CORS_ORIGINS=*

# Production (restrict to specific domains)
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### Session Settings

```env
SESSION_COOKIE_SAMESITE=None   # None, Lax, or Strict
SESSION_COOKIE_SECURE=True     # Require HTTPS (True/False)
```

### JWT Settings

```env
JWT_ACCESS_TOKEN_EXPIRES_HOURS=5    # Access token lifetime in hours
JWT_REFRESH_TOKEN_EXPIRES_DAYS=60   # Refresh token lifetime in days
JWT_TOKEN_LOCATION=headers          # Where to look for JWT token
JWT_HEADER_NAME=Authorization       # Header name for JWT
JWT_HEADER_TYPE=Bearer              # Header type (Bearer, JWT, etc.)
```

### AI Server URLs

```env
# Semantic object detection (required)
AI_OBJECT_DETECTION_URL=http://192.168.1.79:8888

# Road boundary detection (optional)
AI_ROAD_BOUNDARY_URL=http://192.168.1.79:8889

# OpenStreetMap routing server
OPENSTREET_URL=http://192.168.1.79:8890
```

### Roadview API Keys

```env
# Google Street View API
GOOGLE_MAPS_API_KEY=your-google-api-key-here

# Kakao Map API (Korean maps)
KAKAO_REST_API_KEY=your-kakao-api-key-here

# Naver Map API (Korean maps)
NAVER_CLIENT_ID=your-naver-client-id-here
NAVER_CLIENT_SECRET=your-naver-client-secret-here
```

Leave empty if not using roadview features.

### File Upload Settings

```env
# Maximum file upload size in MB
MAX_CONTENT_LENGTH_MB=16

# Upload directory path
UPLOAD_FOLDER=app/static
```

### Static Files

```env
STATIC_FOLDER=static
STATIC_URL_PATH=/static
```

---

## 🔐 Security Best Practices

### Development Environment (`.env.local`)

- ✓ Can use simple passwords for testing
- ✓ Can allow all CORS origins (`*`)
- ✓ Can enable SQL query logging
- ✓ Can use HTTP for local testing

### Production Environment (`.env.production`)

- ✗ **NEVER** use default/simple passwords
- ✗ **NEVER** commit `.env.production` to git
- ✗ **NEVER** allow all CORS origins in production
- ✓ **ALWAYS** generate secure random keys
- ✓ **ALWAYS** use HTTPS
- ✓ **ALWAYS** restrict CORS to your domain
- ✓ **ALWAYS** disable SQL query logging
- ✓ **ALWAYS** use strong database passwords

---

## 🧪 Testing Your Configuration

### Check if environment is loaded:

```powershell
python -c "from apps.config.common import Config; print(Config.SQLALCHEMY_DATABASE_URI)"
```

### Start Flask with your configuration:

```powershell
# Development
$env:FLASK_ENV="development"
python apps/app.py

# Production
$env:FLASK_ENV="production"
python apps/app.py
```

---

## 📝 Example Configurations

### Example: Development Setup

```env
# .env.local
FLASK_ENV=development
FLASK_DEBUG=True

SECRET_KEY=dev-secret-key-not-for-production
JWT_SECRET_KEY=dev-jwt-key-not-for-production

DB_HOST=localhost
DB_PORT=3306
DB_USER=dev_user
DB_PASSWORD=dev_pass
DB_NAME=404found_dev

SQLALCHEMY_ECHO=True
CORS_ORIGINS=*

AI_OBJECT_DETECTION_URL=http://localhost:8888
AI_ROAD_BOUNDARY_URL=http://localhost:8889
OPENSTREET_URL=http://localhost:8890
```

### Example: Production Setup

```env
# .env.production
FLASK_ENV=production
FLASK_DEBUG=False

SECRET_KEY=xvB9mP2nQ7wL4kR8tY6uI3oP5aS1dF4gH9jK2lZ0xC8vB6nM4qW7eR3tY5uI9oP
JWT_SECRET_KEY=aB5cD8eF2gH9iJ3kL7mN0pQ4rS6tU1vW9xY2zA6bC4dE8fG3hI7jK1lM5nO9pQ

DB_HOST=production-db.example.com
DB_PORT=3306
DB_USER=prod_user
DB_PASSWORD=SecureProductionPassword123!@#
DB_NAME=404found_production

SQLALCHEMY_ECHO=False
CORS_ORIGINS=https://yourdomain.com,https://api.yourdomain.com

SESSION_COOKIE_SAMESITE=Lax
SESSION_COOKIE_SECURE=True

AI_OBJECT_DETECTION_URL=http://ai-server.internal:8888
AI_ROAD_BOUNDARY_URL=http://ai-server.internal:8889
OPENSTREET_URL=http://osrm-server.internal:8890

GOOGLE_MAPS_API_KEY=AIzaSyD...your-actual-key...
KAKAO_REST_API_KEY=abc123...your-actual-key...
NAVER_CLIENT_ID=your-actual-client-id
NAVER_CLIENT_SECRET=your-actual-client-secret

MAX_CONTENT_LENGTH_MB=10
```

---

## 🛠️ Troubleshooting

### Problem: Configuration not loading

**Check file exists:**
```powershell
Test-Path .env.local
```

**Check file content:**
```powershell
Get-Content .env.local
```

### Problem: Database connection error

**Verify database settings:**
```powershell
# Test database connection
python -c "from apps.config.common import Config; print(f'Connecting to: {Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}')"
```

### Problem: API keys not working

**Check if keys are loaded:**
```powershell
python -c "from apps.config.common import Config; print(f'Google: {Config.GOOGLE_MAPS_API_KEY[:10]}...')"
```

### Problem: Secret keys are the same every run

**This is normal!** Keys are loaded from `.env` file and stay consistent across runs. Generate new keys only when needed.

---

## 📦 Files Created

- ✅ `.env.local` - Development configuration (edit this for local development)
- ✅ `.env.production` - Production configuration (edit this before deployment)
- ✅ `.env.example` - Template file (copy this to create new environments)
- ✅ `apps/config/common.py` - Updated to read from environment variables
- ⚠️ `.gitignore` - Attempted to update (may already exist)

---

## 🎯 Next Steps

1. **Edit `.env.local`** with your development settings:
   ```powershell
   notepad .env.local
   ```

2. **Test the configuration**:
   ```powershell
   python apps/app.py
   ```

3. **For production deployment**, edit `.env.production`:
   ```powershell
   notepad .env.production
   ```

4. **Generate production keys**:
   ```powershell
   python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
   python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"
   ```

---

## 💡 Tips

- Keep `.env.local` for your personal development settings
- Share `.env.example` with your team (safe to commit)
- Never commit `.env.local` or `.env.production` to git
- Use different database names for dev/prod
- Test configuration changes in development first
- Back up your production `.env.production` file securely

---

**All configurations are now externalized!** Edit the `.env.local` file to customize your settings.
