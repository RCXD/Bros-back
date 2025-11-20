# 📱 Mobile HTTPS Connection Test Guide

Complete guide for testing mobile photo uploads (gallery + camera) with HTTPS.

---

## 🚀 Quick Start

### Option 1: Python Test Script (Automated)

```powershell
# Run all tests
python test/mobile_connection_test.py --url https://your-server.com

# Run specific tests
python test/mobile_connection_test.py --url https://your-server.com --test test_gallery_upload_simulation

# Test with HTTP (development only)
python test/mobile_connection_test.py --url http://localhost:5000 --no-https
```

### Option 2: HTML Test Page (Real Device)

1. **Start your Flask server:**
   ```powershell
   python apps/app.py
   ```

2. **Serve the test page:**
   ```powershell
   # Using Python's built-in server
   cd test
   python -m http.server 8080
   ```

3. **Access from mobile:**
   - Find your computer's IP: `ipconfig` (look for IPv4)
   - Open on mobile: `http://YOUR_IP:8080/mobile_upload_test.html`
   - Example: `http://192.168.1.100:8080/mobile_upload_test.html`

---

## 🔧 Setup Requirements

### 1. Flask Server Configuration

Make sure your Flask app allows CORS for mobile testing:

```python
# In apps/app.py or app/__init__.py
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": "*",  # For testing only! Restrict in production
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})
```

### 2. Install CORS Extension

```powershell
pip install flask-cors
```

### 3. HTTPS Configuration (Production)

For production testing, you'll need SSL certificates:

```powershell
# Generate self-signed certificate (development)
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365

# Run Flask with HTTPS
python apps/app.py --cert cert.pem --key key.pem
```

Or use Let's Encrypt for production certificates.

---

## 📝 Test Scenarios

### Python Script Tests

The `mobile_connection_test.py` script includes 11 comprehensive tests:

1. **test_connection** - Basic HTTPS connectivity
2. **test_ssl_certificate** - SSL/TLS validation
3. **test_authentication** - JWT token acquisition
4. **test_single_photo_upload** - Single image upload
5. **test_multiple_photos_upload** - Multiple images (3 photos)
6. **test_gallery_upload_simulation** - High-res gallery photo (12MP, 4000x3000)
7. **test_camera_upload_simulation** - Camera capture (portrait 4032x3024)
8. **test_large_file_upload** - Large file handling (5MB+)
9. **test_mobile_headers** - iOS/Android User-Agent testing
10. **test_cors_headers** - CORS preflight validation
11. **test_error_handling** - Error scenarios

### HTML Page Features

The `mobile_upload_test.html` page provides:

- **Real Camera Access**: Use device camera to take photos
- **Gallery Selection**: Choose existing photos from gallery
- **Multiple Upload**: Select and upload multiple photos at once
- **Progress Tracking**: Visual upload progress bar
- **Device Info**: Display device and connection details
- **Authentication**: Login with JWT before upload
- **Preview**: See selected photos before upload

---

## 🎯 Testing Workflow

### Step 1: Backend Verification

```powershell
# Test basic connectivity
python test/mobile_connection_test.py --url http://localhost:5000 --no-https --test test_connection

# Test authentication
python test/mobile_connection_test.py --url http://localhost:5000 --no-https --test test_authentication
```

### Step 2: Upload Simulation

```powershell
# Test gallery upload (high-res photo)
python test/mobile_connection_test.py --url http://localhost:5000 --no-https --test test_gallery_upload_simulation

# Test camera upload (portrait orientation)
python test/mobile_connection_test.py --url http://localhost:5000 --no-https --test test_camera_upload_simulation

# Test multiple photos
python test/mobile_connection_test.py --url http://localhost:5000 --no-https --test test_multiple_photos_upload
```

### Step 3: Real Device Testing

1. **Connect device to same WiFi** as your computer
2. **Open HTML page** on mobile browser
3. **Login** with test credentials
4. **Test camera**: Tap "Take Photo" button
5. **Test gallery**: Tap "Choose from Gallery"
6. **Test multiple**: Select multiple photos
7. **Upload**: Tap "Upload Selected Photos"

### Step 4: Production Testing

```powershell
# Test with HTTPS
python test/mobile_connection_test.py --url https://your-production-server.com

# Check SSL certificate
python test/mobile_connection_test.py --url https://your-production-server.com --test test_ssl_certificate
```

---

## 🔍 Common Issues & Solutions

### Issue 1: CORS Errors

**Symptom**: "Access to XMLHttpRequest has been blocked by CORS policy"

**Solution**:
```python
# Add to your Flask app
from flask_cors import CORS
CORS(app, origins=["http://192.168.1.100:8080"])  # Your test server
```

### Issue 2: SSL Certificate Errors

**Symptom**: "SSL: CERTIFICATE_VERIFY_FAILED"

**Solutions**:
- For development: Use `--no-https` flag
- For self-signed certs: Add exception in browser/code
- For production: Use valid SSL certificate (Let's Encrypt)

### Issue 3: Large File Upload Fails

**Symptom**: 413 Request Entity Too Large

**Solution**:
```python
# In Flask config
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit
```

### Issue 4: Camera Not Working on iOS

**Symptom**: Camera button does nothing on iOS

**Solution**:
- iOS requires HTTPS for camera access
- Use valid SSL certificate or test on Android first

### Issue 5: Authentication Token Expired

**Symptom**: 401 Unauthorized after upload

**Solution**:
```python
# Increase token expiration in config
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
```

---

## 📊 Expected Test Results

### Successful Upload Response

```json
{
  "id": 123,
  "content": "Uploaded 3 photo(s) from mobile",
  "images": [
    {
      "id": 456,
      "url": "/static/post_images/2024/01/15/image1.jpg",
      "size": 2048576
    }
  ],
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Python Script Output

```
=== Mobile Photo Upload Test ===
Testing connection to: http://localhost:5000

✓ test_connection - PASSED
✓ test_authentication - PASSED
✓ test_single_photo_upload - PASSED
✓ test_gallery_upload_simulation - PASSED
✓ test_camera_upload_simulation - PASSED

=== Test Summary ===
Total: 11 tests
Passed: 11 ✓
Failed: 0 ✗
Success Rate: 100.0%
```

---

## 🔐 Security Considerations

### Development Environment

- ✓ Use HTTP for local testing
- ✓ Allow all CORS origins
- ✓ Use simple passwords
- ✓ Self-signed certificates OK

### Production Environment

- ✗ NEVER use HTTP - HTTPS only
- ✗ Restrict CORS to specific domains
- ✗ Enforce strong passwords
- ✗ Use valid SSL certificates (Let's Encrypt)
- ✓ Enable rate limiting
- ✓ Validate file types and sizes
- ✓ Scan uploaded files for malware
- ✓ Use secure JWT configuration

---

## 📱 Mobile Browser Testing Matrix

| Browser | Camera | Gallery | Multiple | CORS |
|---------|--------|---------|----------|------|
| iOS Safari | ✓ (HTTPS only) | ✓ | ✓ | ✓ |
| iOS Chrome | ✓ (HTTPS only) | ✓ | ✓ | ✓ |
| Android Chrome | ✓ | ✓ | ✓ | ✓ |
| Android Firefox | ✓ | ✓ | ✓ | ✓ |
| Android Samsung Browser | ✓ | ✓ | ✓ | ✓ |

---

## 🎨 Image Specifications Tested

### Gallery Photos (High Resolution)
- **Resolution**: 4000×3000 (12MP)
- **Orientation**: Landscape
- **Quality**: 95% JPEG
- **Expected Size**: 2-4 MB
- **Format**: JPEG
- **Use Case**: High-quality uploads from saved photos

### Camera Photos (Live Capture)
- **Resolution**: 3024×4032 (portrait)
- **Orientation**: Portrait (EXIF orientation tag)
- **Quality**: 85% JPEG
- **Expected Size**: 1-3 MB
- **Format**: JPEG
- **Use Case**: Real-time camera captures

### Multiple Photos
- **Count**: 3 photos
- **Total Size**: ~3-6 MB
- **Batch Upload**: All photos in single request
- **Use Case**: Album uploads, multiple views

---

## 🛠️ Advanced Configuration

### Custom Test Credentials

Edit the Python script:
```python
# In mobile_connection_test.py
self.email = "your-test-user@example.com"
self.password = "your-test-password"
```

Or HTML page:
```html
<!-- In mobile_upload_test.html -->
<input type="email" id="email" value="your-test-user@example.com">
<input type="password" id="password" value="your-test-password">
```

### Custom Upload Endpoint

```python
# In mobile_connection_test.py
UPLOAD_ENDPOINT = "/api/v1/posts"  # Change to your endpoint

# In mobile_upload_test.html
xhr.open('POST', `${API_URL}/api/v1/posts`);  // Change endpoint
```

### Adjust Image Quality

```python
# In mobile_connection_test.py
test_image.save(buffer, format='JPEG', quality=95, optimize=True)
```

---

## 📖 API Endpoint Reference

### POST /post (Upload Photos)

**Headers:**
```
Authorization: Bearer <jwt_token>
Content-Type: multipart/form-data
```

**Form Data:**
- `content` (string): Post caption/description
- `category_id` (integer): Category ID
- `images` (file[]): One or more image files

**Response (201 Created):**
```json
{
  "id": 123,
  "content": "Post content",
  "images": [...],
  "created_at": "2024-01-15T10:30:00Z"
}
```

### POST /auth/login (Authentication)

**Body:**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {...}
}
```

---

## 📞 Support & Debugging

### Enable Debug Logging

```python
# In mobile_connection_test.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Server Logs

```powershell
# View Flask logs
python apps/app.py  # Check console output

# Or check log file
Get-Content -Path logs/app.log -Wait -Tail 50
```

### Network Inspection

On mobile device:
1. iOS: Settings → Safari → Advanced → Web Inspector
2. Android: Chrome → DevTools → Remote Devices
3. Use browser's Network tab to inspect requests

---

## ✅ Checklist

Before mobile testing:
- [ ] Flask server is running
- [ ] CORS is configured
- [ ] Test user account exists
- [ ] Upload directory has write permissions
- [ ] Firewall allows connections (if testing from mobile)
- [ ] SSL certificate valid (if using HTTPS)
- [ ] MAX_CONTENT_LENGTH configured for large files

After successful tests:
- [ ] All Python tests passed
- [ ] Camera upload works on mobile
- [ ] Gallery upload works on mobile
- [ ] Multiple photos upload works
- [ ] Progress bar displays correctly
- [ ] Error handling works
- [ ] Authentication flow complete
- [ ] Files saved to correct directory

---

## 🎉 Success Indicators

You've successfully tested mobile uploads when:

1. ✅ Python script shows 100% pass rate
2. ✅ Mobile HTML page can access camera
3. ✅ Photos upload from gallery
4. ✅ Progress bar shows 100% completion
5. ✅ Server confirms receipt with 201 status
6. ✅ Images saved to `app/static/post_images/`
7. ✅ Database records created
8. ✅ No CORS errors in console
9. ✅ SSL certificate valid (production)
10. ✅ Large files (5MB+) upload successfully

---

## 📚 Additional Resources

- [Flask-CORS Documentation](https://flask-cors.readthedocs.io/)
- [MDN: Using camera on web](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)
- [Let's Encrypt](https://letsencrypt.org/) - Free SSL certificates
- [HTML5 File API](https://developer.mozilla.org/en-US/docs/Web/API/File_API)

---

**Need help?** Check server logs, browser console, and Network tab for detailed error messages.
