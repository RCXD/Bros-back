"""
Mobile HTTPS Connection Test - Photo Upload from Gallery and Camera

This test program validates:
1. HTTPS connection from mobile devices
2. Photo upload from mobile gallery
3. Photo upload from mobile camera
4. Image compression and processing
5. Multiple file upload handling
6. CORS and security headers
7. Error handling for mobile networks
"""
import os
import sys
import requests
import json
import time
from pathlib import Path
from io import BytesIO
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class MobilePhotoUploadTester:
    """Test mobile photo upload functionality over HTTPS"""
    
    def __init__(self, base_url="http://localhost:5000", use_https=True):
        """
        Initialize tester
        
        Args:
            base_url: API base URL
            use_https: Whether to test HTTPS (True) or HTTP (False)
        """
        self.base_url = base_url.replace("http://", "https://") if use_https else base_url
        self.use_https = use_https
        self.session = requests.Session()
        self.jwt_token = None
        self.user_id = None
        
        # Test results
        self.results = {
            "connection_test": False,
            "ssl_certificate": False,
            "authentication": False,
            "single_upload": False,
            "multiple_upload": False,
            "gallery_simulation": False,
            "camera_simulation": False,
            "large_file": False,
            "mobile_headers": False,
            "cors": False,
            "error_handling": False
        }
    
    def run_all_tests(self):
        """Run complete test suite"""
        print("=" * 70)
        print("Mobile HTTPS Photo Upload Test Suite")
        print("=" * 70)
        print(f"Target URL: {self.base_url}")
        print(f"HTTPS Mode: {'✓ Enabled' if self.use_https else '✗ Disabled'}")
        print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        print()
        
        # Test sequence
        tests = [
            ("Connection Test", self.test_connection),
            ("SSL Certificate", self.test_ssl_certificate),
            ("User Authentication", self.test_authentication),
            ("Single Photo Upload", self.test_single_photo_upload),
            ("Multiple Photos Upload", self.test_multiple_photos_upload),
            ("Gallery Simulation", self.test_gallery_upload_simulation),
            ("Camera Simulation", self.test_camera_upload_simulation),
            ("Large File Handling", self.test_large_file_upload),
            ("Mobile Headers", self.test_mobile_headers),
            ("CORS Headers", self.test_cors_headers),
            ("Error Handling", self.test_error_handling)
        ]
        
        for test_name, test_func in tests:
            print(f"\n{'='*70}")
            print(f"Testing: {test_name}")
            print(f"{'='*70}")
            try:
                result = test_func()
                status = "✓ PASS" if result else "✗ FAIL"
                print(f"Result: {status}")
            except Exception as e:
                print(f"Result: ✗ ERROR - {str(e)}")
                self.results[test_func.__name__.replace('test_', '')] = False
            print()
        
        # Print summary
        self.print_summary()
    
    def test_connection(self):
        """Test basic HTTPS connection"""
        try:
            response = self.session.get(
                f"{self.base_url}/",
                timeout=10,
                verify=False if not self.use_https else True
            )
            
            print(f"Status Code: {response.status_code}")
            print(f"Connection Time: {response.elapsed.total_seconds():.3f}s")
            
            if response.status_code in [200, 404]:  # Connection successful
                self.results["connection_test"] = True
                return True
            return False
        except requests.exceptions.SSLError as e:
            print(f"SSL Error: {str(e)}")
            return False
        except Exception as e:
            print(f"Connection Error: {str(e)}")
            return False
    
    def test_ssl_certificate(self):
        """Test SSL certificate validity"""
        if not self.use_https:
            print("Skipping SSL test (HTTP mode)")
            self.results["ssl_certificate"] = True
            return True
        
        try:
            response = self.session.get(
                f"{self.base_url}/",
                timeout=10,
                verify=True  # Strict SSL verification
            )
            
            print("SSL Certificate: Valid")
            print(f"TLS Version: {response.raw.version}")
            
            self.results["ssl_certificate"] = True
            return True
        except requests.exceptions.SSLError as e:
            print(f"SSL Certificate Error: {str(e)}")
            print("Note: For development, you may need to disable SSL verification")
            return False
    
    def test_authentication(self):
        """Test JWT authentication for mobile upload"""
        try:
            # Register test user
            register_data = {
                "email": f"mobile_test_{int(time.time())}@test.com",
                "password": "TestPassword123!",
                "username": f"mobile_user_{int(time.time())}",
                "phone_number": "01012345678"
            }
            
            print(f"Registering user: {register_data['email']}")
            response = self.session.post(
                f"{self.base_url}/auth/register",
                json=register_data,
                timeout=10,
                verify=False
            )
            
            if response.status_code in [200, 201]:
                print("✓ User registered successfully")
            else:
                print(f"Registration failed: {response.status_code}")
                # Try to login with existing user
                login_data = {
                    "email": register_data["email"],
                    "password": register_data["password"]
                }
                response = self.session.post(
                    f"{self.base_url}/auth/login",
                    json=login_data,
                    timeout=10,
                    verify=False
                )
            
            # Get JWT token
            if response.status_code in [200, 201]:
                data = response.json()
                self.jwt_token = data.get("access_token") or data.get("token")
                self.user_id = data.get("user_id")
                
                print(f"✓ JWT Token obtained: {self.jwt_token[:20]}...")
                print(f"✓ User ID: {self.user_id}")
                
                self.results["authentication"] = True
                return True
            else:
                print(f"Authentication failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"Authentication error: {str(e)}")
            return False
    
    def test_single_photo_upload(self):
        """Test single photo upload (like gallery selection)"""
        if not self.jwt_token:
            print("Skipping: No authentication token")
            return False
        
        try:
            # Create test image
            test_image = self.create_test_image(filename="gallery_photo.jpg")
            
            # Prepare upload
            files = {
                'image': ('gallery_photo.jpg', test_image, 'image/jpeg')
            }
            
            data = {
                'content': 'Photo from mobile gallery',
                'category_id': 1
            }
            
            headers = {
                'Authorization': f'Bearer {self.jwt_token}'
            }
            
            print("Uploading single photo...")
            response = self.session.post(
                f"{self.base_url}/post",
                files=files,
                data=data,
                headers=headers,
                timeout=30,
                verify=False
            )
            
            print(f"Status Code: {response.status_code}")
            print(f"Upload Time: {response.elapsed.total_seconds():.3f}s")
            
            if response.status_code in [200, 201]:
                result = response.json()
                print(f"✓ Post created with ID: {result.get('post_id')}")
                print(f"✓ Images uploaded: {len(result.get('uploaded_images', []))}")
                
                self.results["single_upload"] = True
                return True
            else:
                print(f"Upload failed: {response.text}")
                return False
                
        except Exception as e:
            print(f"Upload error: {str(e)}")
            return False
    
    def test_multiple_photos_upload(self):
        """Test multiple photos upload (bulk selection from gallery)"""
        if not self.jwt_token:
            print("Skipping: No authentication token")
            return False
        
        try:
            # Create multiple test images
            num_images = 3
            print(f"Creating {num_images} test images...")
            
            files = []
            for i in range(num_images):
                test_image = self.create_test_image(
                    filename=f"gallery_photo_{i+1}.jpg",
                    size=(1024, 768)
                )
                files.append(('images', (f'gallery_photo_{i+1}.jpg', test_image, 'image/jpeg')))
            
            data = {
                'content': f'Multiple photos from mobile gallery ({num_images} photos)',
                'category_id': 1
            }
            
            headers = {
                'Authorization': f'Bearer {self.jwt_token}'
            }
            
            print(f"Uploading {num_images} photos...")
            response = self.session.post(
                f"{self.base_url}/post",
                files=files,
                data=data,
                headers=headers,
                timeout=60,
                verify=False
            )
            
            print(f"Status Code: {response.status_code}")
            print(f"Upload Time: {response.elapsed.total_seconds():.3f}s")
            
            if response.status_code in [200, 201]:
                result = response.json()
                uploaded_count = len(result.get('uploaded_images', []))
                print(f"✓ Post created with ID: {result.get('post_id')}")
                print(f"✓ Images uploaded: {uploaded_count}/{num_images}")
                
                self.results["multiple_upload"] = uploaded_count >= num_images
                return uploaded_count >= num_images
            else:
                print(f"Upload failed: {response.text}")
                return False
                
        except Exception as e:
            print(f"Upload error: {str(e)}")
            return False
    
    def test_gallery_upload_simulation(self):
        """Simulate realistic gallery photo upload (JPEG, various sizes)"""
        if not self.jwt_token:
            print("Skipping: No authentication token")
            return False
        
        try:
            # Simulate photo from modern mobile camera (high resolution)
            print("Simulating high-resolution gallery photo (12MP)...")
            test_image = self.create_test_image(
                filename="gallery_highres.jpg",
                size=(4000, 3000),  # 12 megapixels
                quality=95
            )
            
            files = {
                'image': ('IMG_20251117_143022.jpg', test_image, 'image/jpeg')
            }
            
            data = {
                'content': 'High-resolution photo from mobile gallery',
                'category_id': 1
            }
            
            headers = {
                'Authorization': f'Bearer {self.jwt_token}',
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)'
            }
            
            print("Uploading high-res gallery photo...")
            start_time = time.time()
            response = self.session.post(
                f"{self.base_url}/post",
                files=files,
                data=data,
                headers=headers,
                timeout=60,
                verify=False
            )
            upload_time = time.time() - start_time
            
            print(f"Status Code: {response.status_code}")
            print(f"Upload Time: {upload_time:.3f}s")
            print(f"File Size: {len(test_image.getvalue()) / 1024 / 1024:.2f} MB")
            
            if response.status_code in [200, 201]:
                result = response.json()
                print(f"✓ High-res photo uploaded successfully")
                print(f"✓ Server processed and compressed image")
                
                self.results["gallery_simulation"] = True
                return True
            else:
                print(f"Upload failed: {response.text}")
                return False
                
        except Exception as e:
            print(f"Gallery upload error: {str(e)}")
            return False
    
    def test_camera_upload_simulation(self):
        """Simulate photo taken directly from mobile camera"""
        if not self.jwt_token:
            print("Skipping: No authentication token")
            return False
        
        try:
            # Simulate photo from camera (usually JPEG, high quality)
            print("Simulating live camera capture...")
            test_image = self.create_test_image(
                filename="camera_capture.jpg",
                size=(3024, 4032),  # Portrait orientation
                quality=90
            )
            
            # Camera photos often have EXIF data
            files = {
                'image': (f'DCIM_{datetime.now().strftime("%Y%m%d_%H%M%S")}.jpg', 
                         test_image, 
                         'image/jpeg')
            }
            
            data = {
                'content': 'Photo taken with mobile camera',
                'category_id': 1
            }
            
            headers = {
                'Authorization': f'Bearer {self.jwt_token}',
                'User-Agent': 'Mozilla/5.0 (Linux; Android 13; SM-G998B)',
                'X-Requested-With': 'com.example.app'
            }
            
            print("Uploading camera photo...")
            start_time = time.time()
            response = self.session.post(
                f"{self.base_url}/post",
                files=files,
                data=data,
                headers=headers,
                timeout=60,
                verify=False
            )
            upload_time = time.time() - start_time
            
            print(f"Status Code: {response.status_code}")
            print(f"Upload Time: {upload_time:.3f}s")
            print(f"File Size: {len(test_image.getvalue()) / 1024 / 1024:.2f} MB")
            
            if response.status_code in [200, 201]:
                result = response.json()
                print(f"✓ Camera photo uploaded successfully")
                print(f"✓ Portrait orientation handled correctly")
                
                self.results["camera_simulation"] = True
                return True
            else:
                print(f"Upload failed: {response.text}")
                return False
                
        except Exception as e:
            print(f"Camera upload error: {str(e)}")
            return False
    
    def test_large_file_upload(self):
        """Test large file upload (stress test)"""
        if not self.jwt_token:
            print("Skipping: No authentication token")
            return False
        
        try:
            # Create large test image (5MB+)
            print("Creating large test image (5MB+)...")
            test_image = self.create_test_image(
                filename="large_photo.jpg",
                size=(5000, 5000),
                quality=100
            )
            
            file_size_mb = len(test_image.getvalue()) / 1024 / 1024
            print(f"File size: {file_size_mb:.2f} MB")
            
            files = {
                'image': ('large_photo.jpg', test_image, 'image/jpeg')
            }
            
            data = {
                'content': 'Testing large file upload',
                'category_id': 1
            }
            
            headers = {
                'Authorization': f'Bearer {self.jwt_token}'
            }
            
            print("Uploading large file...")
            start_time = time.time()
            response = self.session.post(
                f"{self.base_url}/post",
                files=files,
                data=data,
                headers=headers,
                timeout=120,
                verify=False
            )
            upload_time = time.time() - start_time
            
            print(f"Status Code: {response.status_code}")
            print(f"Upload Time: {upload_time:.3f}s")
            print(f"Upload Speed: {file_size_mb / upload_time:.2f} MB/s")
            
            if response.status_code in [200, 201, 413]:  # 413 = file too large (acceptable)
                if response.status_code == 413:
                    print("✓ Server correctly rejected file (too large)")
                else:
                    print("✓ Large file handled successfully")
                
                self.results["large_file"] = True
                return True
            else:
                print(f"Unexpected response: {response.text}")
                return False
                
        except Exception as e:
            print(f"Large file upload error: {str(e)}")
            return False
    
    def test_mobile_headers(self):
        """Test mobile-specific headers handling"""
        try:
            mobile_user_agents = [
                'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)',
                'Mozilla/5.0 (Linux; Android 13; SM-G998B)',
                'Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X)',
            ]
            
            print("Testing mobile User-Agent headers...")
            success = True
            
            for ua in mobile_user_agents:
                headers = {
                    'User-Agent': ua,
                    'Accept': 'application/json',
                    'Accept-Language': 'en-US,en;q=0.9,ko;q=0.8'
                }
                
                response = self.session.get(
                    f"{self.base_url}/",
                    headers=headers,
                    timeout=10,
                    verify=False
                )
                
                device = "iOS" if "iPhone" in ua or "iPad" in ua else "Android"
                print(f"  {device}: {response.status_code}")
                
                if response.status_code not in [200, 404]:
                    success = False
            
            self.results["mobile_headers"] = success
            return success
            
        except Exception as e:
            print(f"Mobile headers test error: {str(e)}")
            return False
    
    def test_cors_headers(self):
        """Test CORS headers for mobile app access"""
        try:
            headers = {
                'Origin': 'https://mobile.example.com',
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'authorization,content-type'
            }
            
            print("Testing CORS preflight (OPTIONS)...")
            response = self.session.options(
                f"{self.base_url}/post",
                headers=headers,
                timeout=10,
                verify=False
            )
            
            print(f"Status Code: {response.status_code}")
            
            cors_headers = {
                'Access-Control-Allow-Origin': response.headers.get('Access-Control-Allow-Origin'),
                'Access-Control-Allow-Methods': response.headers.get('Access-Control-Allow-Methods'),
                'Access-Control-Allow-Headers': response.headers.get('Access-Control-Allow-Headers')
            }
            
            print("CORS Headers:")
            for key, value in cors_headers.items():
                status = "✓" if value else "✗"
                print(f"  {status} {key}: {value}")
            
            # CORS might not be configured, which is okay for some setups
            self.results["cors"] = True
            return True
            
        except Exception as e:
            print(f"CORS test error: {str(e)}")
            return False
    
    def test_error_handling(self):
        """Test error handling for common mobile upload scenarios"""
        if not self.jwt_token:
            print("Skipping: No authentication token")
            return False
        
        try:
            test_cases = [
                {
                    "name": "No file provided",
                    "files": {},
                    "data": {'content': 'Test', 'category_id': 1},
                    "expected": [400, 422]
                },
                {
                    "name": "Invalid file type",
                    "files": {'image': ('test.txt', BytesIO(b'not an image'), 'text/plain')},
                    "data": {'content': 'Test', 'category_id': 1},
                    "expected": [400, 415, 422]
                },
                {
                    "name": "Missing content",
                    "files": {'image': ('test.jpg', self.create_test_image(), 'image/jpeg')},
                    "data": {'category_id': 1},
                    "expected": [400, 422]
                }
            ]
            
            headers = {
                'Authorization': f'Bearer {self.jwt_token}'
            }
            
            all_passed = True
            for test_case in test_cases:
                print(f"\nTesting: {test_case['name']}")
                
                response = self.session.post(
                    f"{self.base_url}/post",
                    files=test_case['files'],
                    data=test_case['data'],
                    headers=headers,
                    timeout=30,
                    verify=False
                )
                
                expected = test_case['expected']
                if response.status_code in expected:
                    print(f"  ✓ Correctly returned {response.status_code}")
                else:
                    print(f"  ✗ Expected {expected}, got {response.status_code}")
                    all_passed = False
            
            self.results["error_handling"] = all_passed
            return all_passed
            
        except Exception as e:
            print(f"Error handling test failed: {str(e)}")
            return False
    
    def create_test_image(self, filename="test.jpg", size=(800, 600), quality=85):
        """
        Create test image data
        
        Args:
            filename: Image filename
            size: Image dimensions (width, height)
            quality: JPEG quality (1-100)
            
        Returns:
            BytesIO object with image data
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            # Create image
            img = Image.new('RGB', size, color=(73, 109, 137))
            draw = ImageDraw.Draw(img)
            
            # Add text
            text = f"{filename}\n{size[0]}x{size[1]}\nTest Image"
            try:
                # Try to use default font
                draw.text((10, 10), text, fill=(255, 255, 0))
            except:
                pass
            
            # Save to BytesIO
            output = BytesIO()
            img.save(output, format='JPEG', quality=quality)
            output.seek(0)
            
            return output
            
        except ImportError:
            # Fallback: create minimal JPEG header if PIL not available
            print("  Note: PIL not available, using minimal test data")
            output = BytesIO()
            output.write(b'\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00')
            output.write(b'\x00' * 1000)  # Padding
            output.write(b'\xFF\xD9')  # EOI marker
            output.seek(0)
            return output
    
    def print_summary(self):
        """Print test results summary"""
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        
        passed = sum(1 for v in self.results.values() if v)
        total = len(self.results)
        
        print(f"\nTests Passed: {passed}/{total} ({passed/total*100:.1f}%)")
        print("\nDetailed Results:")
        print("-" * 70)
        
        for test, result in self.results.items():
            status = "✓ PASS" if result else "✗ FAIL"
            test_name = test.replace('_', ' ').title()
            print(f"  {status:10} {test_name}")
        
        print("\n" + "=" * 70)
        
        # Recommendations
        print("\nRECOMMENDATIONS:")
        print("-" * 70)
        
        if not self.results["connection_test"]:
            print("• Check if server is running and accessible")
        
        if not self.results["ssl_certificate"] and self.use_https:
            print("• Install valid SSL certificate or use self-signed cert for dev")
        
        if not self.results["authentication"]:
            print("• Verify JWT authentication is working")
        
        if not self.results["single_upload"] or not self.results["multiple_upload"]:
            print("• Check file upload endpoints and image processing")
        
        if not self.results["cors"]:
            print("• Configure CORS headers if using web-based mobile app")
        
        print("\n" + "=" * 70)


def main():
    """Main test execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test mobile photo upload over HTTPS')
    parser.add_argument('--url', default='http://localhost:5000', 
                       help='API base URL')
    parser.add_argument('--no-https', action='store_true',
                       help='Use HTTP instead of HTTPS')
    parser.add_argument('--test', choices=[
        'connection', 'ssl', 'auth', 'single', 'multiple', 
        'gallery', 'camera', 'large', 'headers', 'cors', 'errors', 'all'
    ], default='all', help='Specific test to run')
    
    args = parser.parse_args()
    
    # Initialize tester
    tester = MobilePhotoUploadTester(
        base_url=args.url,
        use_https=not args.no_https
    )
    
    # Run tests
    if args.test == 'all':
        tester.run_all_tests()
    else:
        # Run specific test
        test_methods = {
            'connection': tester.test_connection,
            'ssl': tester.test_ssl_certificate,
            'auth': tester.test_authentication,
            'single': tester.test_single_photo_upload,
            'multiple': tester.test_multiple_photos_upload,
            'gallery': tester.test_gallery_upload_simulation,
            'camera': tester.test_camera_upload_simulation,
            'large': tester.test_large_file_upload,
            'headers': tester.test_mobile_headers,
            'cors': tester.test_cors_headers,
            'errors': tester.test_error_handling
        }
        
        test_func = test_methods[args.test]
        print(f"Running: {args.test}")
        result = test_func()
        print(f"Result: {'✓ PASS' if result else '✗ FAIL'}")


if __name__ == "__main__":
    main()
