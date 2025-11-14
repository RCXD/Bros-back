# Command Reference

Quick reference for executing test data generators from Windows Command Prompt.

## Prerequisites

Set working directory to project root:
```
cd D:\M\GitHub\Bros-back
```

Activate Python virtual environment (if applicable):
```
venv\Scripts\activate
```

## Master Commands

### Generate All Data

| Command | Environment | Mode | Description |
|---------|-------------|------|-------------|
| `python apps\gen\generators\generate_all.py` | Production | Direct | Generate all data with direct storage |
| `python apps\gen\generators\generate_all.py --api` | Production | API | Generate all data via API |
| `python apps\gen\generators\generate_all.py --test` | Test | Direct | Generate all data (test environment) |
| `python apps\gen\generators\generate_all.py --clear --test` | Test | Direct | Clear database then generate |
| `python apps\gen\generators\generate_all.py --clear --api` | Production | API | Clear database then generate via API |

### Verify Database

| Command | Environment | Description |
|---------|-------------|-------------|
| `python apps\gen\generators\verify.py` | Production | Verify production database |
| `python apps\gen\generators\verify.py --test` | Test | Verify test database |

## Individual Generators

### User Generation

| Command | Environment | Users | Admins |
|---------|-------------|-------|--------|
| `python apps\gen\generators\gen_users.py` | Production | 50 | 2 |
| `python apps\gen\generators\gen_users.py --test` | Test | 10 | 2 |

**Prerequisites:** Database must exist

**Output:** Creates user accounts with username (user1, user2, ...), email, hashed password

### Profile Image Generation

| Command | Environment | Mode | Storage Location |
|---------|-------------|------|------------------|
| `python apps\gen\generators\gen_profile_images.py` | Production | API | Remote server |
| `python apps\gen\generators\gen_profile_images.py --test` | Test | Direct | apps\gen\uploads\profile_images |

**Prerequisites:** Users must exist

**Output:** Assigns 512x512 PNG profile images to all users

### Post Generation

| Command | Environment | Source JSON | Categories |
|---------|-------------|-------------|-----------|
| `python apps\gen\generators\gen_posts.py` | Production | apps\gen\data\post_data.json | STORY, ROUTE, REVIEW, REPORT |
| `python apps\gen\generators\gen_posts.py --test` | Test | apps\gen\data\test_post_data.json | STORY, ROUTE, REVIEW, REPORT |

**Prerequisites:** Users must exist

**Output:** Creates posts from JSON data with timestamps and view counts

### Post Image Generation

| Command | Environment | Mode | Images per Post |
|---------|-------------|------|----------------|
| `python apps\gen\generators\gen_post_images.py` | Production | API | 0-3 (random) |
| `python apps\gen\generators\gen_post_images.py --test` | Test | Direct | 0-3 (random) |

**Prerequisites:** Users and posts must exist, categorized source images required

**Output:** Assigns category-matched images to posts (max 1024px width, PNG)

**Folder Mapping:**
- daily → STORY
- route → ROUTE  
- review → REVIEW
- report → REPORT

### Reply Generation

| Command | Environment | Replies per Post | Nested Replies |
|---------|-------------|-----------------|----------------|
| `python apps\gen\generators\gen_replies.py` | Production | 1-6 (avg 3) | 0-3 per post |
| `python apps\gen\generators\gen_replies.py --test` | Test | 1-6 (avg 3) | 0-3 per post |

**Prerequisites:** Users and posts must exist

**Output:** Creates main replies and nested replies with Korean content

## Execution Sequences

### Full Setup (Test Environment)

```
python apps\gen\generators\generate_all.py --clear --test
```

Equivalent to:
```
python apps\gen\generators\gen_users.py --test
python apps\gen\generators\gen_profile_images.py --test
python apps\gen\generators\gen_posts.py --test
python apps\gen\generators\gen_post_images.py --test
python apps\gen\generators\gen_replies.py --test
```

### Full Setup (Production via API)

```
python apps\gen\generators\generate_all.py --clear --api
```

### Regenerate Only Images

```
python apps\gen\generators\gen_profile_images.py --test
python apps\gen\generators\gen_post_images.py --test
```

### Add More Replies

```
python apps\gen\generators\gen_replies.py
```

## Configuration

Configuration file: `apps\gen\.env`

### Switch Between Environments

**Use Test Environment:**
- Add `--test` flag to any command
- Uses TEST_ prefixed variables from .env
- Connects to localhost
- Direct file storage

**Use Production Environment:**
- Default (no flag needed)
- Uses PROD_ prefixed variables from .env
- Connects to remote server
- API-based operations (with --api flag)

### Key Configuration Variables

| Variable | Production | Test |
|----------|-----------|------|
| API_BACKEND_URL | http://192.168.1.86:8000 | http://localhost:5000 |
| DB_HOST | 192.168.1.79 | localhost |
| NUM_USERS | 50 | 10 |
| NUM_ADMINS | 2 | 2 |
| PROFILE_IMG_FOLDER | static\profile_images | apps\gen\uploads\profile_images |
| POST_IMG_FOLDER | static\post_images | apps\gen\uploads\post_images |
| POST_JSON_PATH | apps\gen\data\post_data.json | apps\gen\data\test_post_data.json |

## Flags Summary

| Flag | Purpose | Applicable To |
|------|---------|--------------|
| `--test` | Use test environment configuration | All commands |
| `--api` | Use API mode for image uploads | generate_all.py, image generators |
| `--clear` | Clear database before generation | generate_all.py |

## Output Interpretation

### Success Indicators

**User Generation:**
```
Created 50 users, 2 admins
```

**Profile Images:**
```
Profile images: 50 success, 0 failed
```

**Posts:**
```
Created 120 posts
```

**Post Images:**
```
Post images: 180 success, 0 failed
```

**Replies:**
```
Created 360 replies
```

**Verification:**
```
Users:
  Total: 52
  Regular: 50
  Admins: 2
  With Profile Image: 52
Posts:
  Total: 120
  With Images: 90
  By Category:
    STORY: 40
    ROUTE: 30
    REVIEW: 30
    REPORT: 20
Replies:
  Total: 360
  Main: 300
  Nested: 60
Images:
  Total: 230
  Profile: 52
  Post: 178
Categories: 4
```

## Troubleshooting

| Error Message | Solution |
|--------------|----------|
| No users found | Run `gen_users.py` first |
| No posts found | Run `gen_posts.py` after `gen_users.py` |
| Failed to obtain user tokens | Ensure API server running, check API_BACKEND_URL |
| No images found in directory | Verify DUMMY_*_IMG_DIR paths in .env |
| Database connection error | Check DB_HOST, DB_PORT, DB_NAME in .env |
| Permission denied | Check write permissions on upload directories |
| Image upload failures | Verify API server status and timeout settings |

## Best Practices

1. **Always verify after generation:**
   ```
   python apps\gen\generators\verify.py
   ```

2. **Clear database when changing user counts:**
   ```
   python apps\gen\generators\generate_all.py --clear --test
   ```

3. **Test locally before production:**
   ```
   python apps\gen\generators\generate_all.py --test
   python apps\gen\generators\verify.py --test
   ```

4. **Backup production database before clearing:**
   ```
   mysqldump -h 192.168.1.79 -u root -p 404found_test > backup.sql
   ```

5. **Check image source directories exist:**
   ```
   dir "D:\share\dummy data\profile_images"
   dir "D:\share\dummy data\images\daily"
   dir "D:\share\dummy data\images\route"
   ```

## Quick Reference Card

**Start Fresh (Test):**
```
python apps\gen\generators\generate_all.py --clear --test
python apps\gen\generators\verify.py --test
```

**Start Fresh (Production):**
```
python apps\gen\generators\generate_all.py --clear --api
python apps\gen\generators\verify.py
```

**Add Users Only:**
```
python apps\gen\generators\gen_users.py
```

**Regenerate Images:**
```
python apps\gen\generators\gen_profile_images.py
python apps\gen\generators\gen_post_images.py
```

**Check Status:**
```
python apps\gen\generators\verify.py
```
