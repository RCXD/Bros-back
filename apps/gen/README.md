# Test Data Generator

A clean, production-ready test data generation system for the Bros backend application. This tool generates users, posts, replies, and associated images for both development and production environments.

## Architecture

### Directory Structure

```
apps/gen/
├── config.py                 # Configuration management
├── .env.example             # Environment variable template
├── helpers/                 # Utility modules
│   ├── auth.py             # JWT token authentication
│   ├── image_api.py        # API-based image upload
│   └── image_processing.py # Image resize and conversion
├── generators/             # Data generation modules
│   ├── gen_users.py       # User account generation
│   ├── gen_posts.py       # Post generation from JSON
│   ├── gen_replies.py     # Reply generation
│   ├── gen_profile_images.py  # Profile image assignment
│   ├── gen_post_images.py     # Post image assignment
│   ├── generate_all.py    # Master generation script
│   └── verify.py          # Data verification utility
└── data/                  # JSON data files
    ├── post_data.json     # Production post data
    └── test_post_data.json # Test post data
```

### Key Components

**Configuration System** (`config.py`)
- Environment-aware configuration (production/test)
- PROD_ and TEST_ prefixed environment variables
- Centralized path and parameter management
- Database URI construction

**Helper Modules** (`helpers/`)
- `auth.py`: JWT token acquisition for API authentication
- `image_api.py`: API client for image upload operations
- `image_processing.py`: Image resizing, format conversion, file scanning

**Generator Modules** (`generators/`)
- Independent, reusable generation functions
- Support both direct database access and API-based operations
- Consistent error handling and return values
- Context manager pattern for database operations

## Configuration

### Environment Setup

1. Copy the example environment file:
   ```
   copy apps\gen\.env.example apps\gen\.env
   ```

2. Edit `apps/gen/.env` with your configuration:

**Production Environment (PROD_ prefix)**
- Used by default
- Connects to remote database server
- Uses API for image uploads
- Generates 50 users and 2 admins

**Test Environment (TEST_ prefix)**
- Activated with `--test` flag
- Uses localhost database
- Direct file storage for images
- Generates 10 users and 2 admins

### Configuration Parameters

| Parameter | Purpose | Production Default | Test Default |
|-----------|---------|-------------------|--------------|
| API_BACKEND_URL | API server address | http://192.168.1.86:8000 | http://localhost:5000 |
| DB_HOST | Database host | 192.168.1.79 | localhost |
| DB_PORT | Database port | 3306 | 3306 |
| DB_NAME | Database name | 404found_test | 404found_test |
| NUM_USERS | Regular users to create | 50 | 10 |
| NUM_ADMINS | Admin users to create | 2 | 2 |
| PROFILE_IMG_FOLDER | Profile image storage | static/profile_images | apps/gen/uploads/profile_images |
| POST_IMG_FOLDER | Post image storage | static/post_images | apps/gen/uploads/post_images |
| DUMMY_PROFILE_IMG_DIR | Source profile images | D:\share\dummy data\profile_images | Same |
| DUMMY_POST_IMG_DIR | Source post images | D:\share\dummy data\images | Same |
| POST_JSON_PATH | Post data JSON file | apps/gen/data/post_data.json | apps/gen/data/test_post_data.json |

## Usage

### Quick Start

Generate all test data at once:

```bash
# Production environment (API-based, 50 users)
python apps/gen/generators/generate_all.py --api

# Test environment (direct storage, 10 users)
python apps/gen/generators/generate_all.py --test

# Clear existing data before generation
python apps/gen/generators/generate_all.py --clear --test
```

### Individual Generators

**Generate Users**
```bash
# Production: 50 users + 2 admins
python apps/gen/generators/gen_users.py

# Test: 10 users + 2 admins
python apps/gen/generators/gen_users.py --test
```

**Generate Profile Images**
```bash
# Production: API upload
python apps/gen/generators/gen_profile_images.py

# Test: Direct file storage
python apps/gen/generators/gen_profile_images.py --test
```

**Generate Posts**
```bash
# Production: Uses apps/gen/data/post_data.json
python apps/gen/generators/gen_posts.py

# Test: Uses apps/gen/data/test_post_data.json
python apps/gen/generators/gen_posts.py --test
```

**Generate Post Images**
```bash
# Production: API upload with category matching
python apps/gen/generators/gen_post_images.py

# Test: Direct file storage
python apps/gen/generators/gen_post_images.py --test
```

**Generate Replies**
```bash
# Generate replies for existing posts
python apps/gen/generators/gen_replies.py
python apps/gen/generators/gen_replies.py --test
```

### Verification

Verify generated data:
```bash
# Production database
python apps/gen/generators/verify.py

# Test database
python apps/gen/generators/verify.py --test
```

Output includes:
- User counts (total, regular, admin, with profile images)
- Post counts (total, by category, with images)
- Reply counts (total, main, nested)
- Image counts (total, profile, post)
- Category count

## Data Generation Details

### User Generation

Creates user accounts with:
- Username: user1, user2, ..., userN (and admin1, admin2, ...)
- Email: user1@mail.com, user2@mail.com, ...
- Password: 1234 (hashed)
- Phone: 010-0000-0001, 010-0000-0002, ...
- Default profile image: static/default_profile.jpg

Duplicate prevention: Skips users that already exist in database.

### Post Generation

Loads post data from JSON file with structure:
```json
{
  "posts": [
    {
      "username": "user1",
      "category": "STORY",
      "content": "Post content here"
    }
  ]
}
```

Features:
- Assigns posts to existing users
- Falls back to random user if specified username not found
- Creates categories (STORY, ROUTE, REVIEW, REPORT) if needed
- Random view counts (0-1000)
- Staggered creation timestamps (last 60 days)

### Reply Generation

Generates replies for each post:
- Average 3 replies per post (1-6 range)
- Includes nested replies (replies to replies)
- Nested reply probability: 0-3 per post
- Timestamps after parent post/reply creation
- Uses predefined Korean reply content

### Image Generation

**Profile Images**
- One image per user
- Resized to 512x512 square (center crop)
- PNG format conversion
- Random assignment from source directory
- Circular assignment if more users than images

**Post Images**
- 0-3 images per post (weighted: more likely 1-2)
- Category-based image selection:
  - daily folder → STORY posts
  - route folder → ROUTE posts
  - review folder → REVIEW posts
  - report folder → REPORT posts
- Resized to max 1024px width
- PNG format conversion
- Recursive search in category folders

### Image Processing

All images are processed with:
- Animated format exclusion (GIF, WebP)
- RGBA/RGB color mode conversion
- Lanczos resampling for quality
- PNG optimization
- Automatic UUID-based naming

### Folder Category Mapping

Source images in `DUMMY_POST_IMG_DIR` should be organized:
```
images/
├── daily/     # For STORY category
├── route/     # For ROUTE category
├── review/    # For REVIEW category
└── report/    # For REPORT category
```

Each folder can contain subdirectories. Images are recursively collected.

## Environment Modes

### Test Mode (--test)

Characteristics:
- Localhost database connection
- Direct file storage (no API calls)
- Smaller dataset (10 users)
- Faster generation
- Local upload directories

Use cases:
- Local development
- Unit testing
- Quick iteration
- Offline work

### Production Mode (default)

Characteristics:
- Remote database connection
- API-based image uploads
- Larger dataset (50 users)
- Production-like data volume
- Server integration testing

Use cases:
- Staging environment setup
- Integration testing
- Pre-production validation
- Load testing preparation

## Dependencies

**Required Python packages:**
- Flask and Flask-SQLAlchemy (database ORM)
- python-dotenv (environment variable management)
- Pillow (image processing)
- requests (API client)
- werkzeug (password hashing)
- pymysql (MySQL database driver)

**Database requirements:**
- MySQL/MariaDB server
- Database created: 404found_test (or configured name)
- User with full permissions

**File system requirements:**
- Source dummy images accessible
- Write permissions for upload directories
- Sufficient disk space for processed images

## Implementation Details

### Error Handling

All generators implement consistent error handling:
- Return tuples with success/failure counts
- Raise ValueError for missing prerequisites (e.g., no users found)
- Raise FileNotFoundError for missing source files
- Continue on individual item failures
- Database transaction rollback on critical errors

### Database Operations

Transaction management:
- Uses Flask app context for database access
- Explicit commit after bulk operations
- Foreign key constraint management for cleanup
- Session expiration for API-based operations

### API Integration

API client features:
- Automatic retry logic (3 attempts by default)
- Exponential backoff on failures
- Timeout configuration (120s default)
- JWT token authentication
- Multipart form data upload
- In-memory image processing (no temp files)

### Performance Considerations

Optimization techniques:
- Bulk database inserts where possible
- Session flush for UUID generation
- Image processing in memory (BytesIO)
- Recursive file scanning with glob
- Circular image assignment (no redundant processing)

## Troubleshooting

**"No users found" error**
- Run gen_users.py first before other generators
- Verify database connection
- Check NUM_USERS configuration

**"Failed to obtain user tokens" error**
- Ensure API server is running
- Verify API_BACKEND_URL configuration
- Check network connectivity
- Confirm user credentials (password: 1234)

**"No images found" error**
- Verify DUMMY_*_IMG_DIR paths exist
- Check directory permissions
- Ensure valid image files present (.jpg, .png, etc.)
- Confirm folder structure matches category mapping

**Image upload failures**
- Check API authentication
- Verify upload endpoint functionality
- Review timeout settings
- Check server disk space

**Database connection errors**
- Verify DB_HOST, DB_PORT, DB_NAME settings
- Check database server status
- Confirm user credentials
- Test network connectivity

## Migration from test/database

This system replaces the pytest-based test/database generators with:
- Cleaner architecture (no pytest dependency)
- Better separation of concerns
- Reusable helper modules
- Environment-aware configuration
- Consistent error handling
- Direct Python script execution

Key improvements:
- No test framework overhead
- Simplified execution (python instead of pytest)
- Better suited for production automation
- Clearer code organization
- Reduced dependencies
- More maintainable codebase

## Future Enhancements

Potential additions:
- Command-line argument parsing with argparse
- Progress bars for long-running operations
- Logging to files
- Parallel image processing
- Database backup before generation
- Rollback functionality
- Custom JSON schema validation
- Incremental updates (add N more users)
- Data export utilities
