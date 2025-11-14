# Bros-back Refactored Architecture

## Overview

This document describes the refactored architecture moving from `./app` to `./apps` with a modular blueprint structure.

## Directory Structure

```
apps/
├── app.py                      # Application factory
├── config/
│   ├── common.py              # Shared configuration
│   └── server.py              # Flask extensions (db, jwt, etc.)
├── common/
│   ├── jwt_handlers.py        # JWT callbacks and handlers
│   └── __init__.py
├── auth/                      # Authentication module
│   ├── models.py             # User model
│   ├── views.py              # Auth routes (signup, login, etc.)
│   ├── utils.py              # Auth utilities (token_provider)
│   └── __init__.py
├── user/                      # User profile & social
│   ├── models.py             # Follow, Friend models
│   ├── views.py              # Profile, follow routes
│   └── __init__.py
├── post/                      # Post management
│   ├── models.py             # Post, Like models
│   ├── views.py              # Post CRUD routes
│   ├── utils.py              # Post utilities
│   └── __init__.py
├── reply/                     # Comments & replies
│   ├── models.py             # Reply model
│   ├── views.py              # Reply routes
│   └── __init__.py
├── feed/                      # User feed & timeline
│   ├── views.py              # Feed routes
│   └── __init__.py
├── route/                     # Navigation & routing
│   ├── models.py             # MyPath model
│   ├── views.py              # Route routes
│   └── __init__.py
├── product/                   # Product reviews
│   ├── models.py             # Product models
│   ├── views.py              # Product routes
│   └── __init__.py
├── favorite/                  # Bookmarks & favorites
│   ├── models.py             # Favorite model
│   ├── views.py              # Favorite routes
│   └── __init__.py
├── detector/                  # AI detection services
│   ├── views.py              # Detection routes
│   ├── utils.py              # AI utilities
│   └── __init__.py
├── security/                  # Reports & moderation
│   ├── models.py             # Report models
│   ├── views.py              # Security routes
│   └── __init__.py
├── admin/                     # Admin functions
│   ├── views.py              # Admin routes
│   └── __init__.py
└── test/                      # Testing endpoints
    ├── views.py              # Test routes
    └── __init__.py
```

## Key Changes from Legacy Structure

### 1. **Modular Blueprint Architecture**

**Before (`./app`):**
```python
app/
├── blueprints/
│   ├── auth.py          # All auth code in one file
│   ├── post.py          # All post code in one file
│   └── ...
├── models/
│   ├── user.py
│   ├── post.py
│   └── ...
└── utils/
    ├── user_utils.py
    └── ...
```

**After (`./apps`):**
```python
apps/
├── auth/
│   ├── models.py        # Auth-specific models
│   ├── views.py         # Auth routes
│   └── utils.py         # Auth utilities
├── post/
│   ├── models.py        # Post-specific models
│   ├── views.py         # Post routes
│   └── utils.py         # Post utilities
└── ...
```

### 2. **Configuration Management**

**Before:**
- Single `config.py` file
- No environment-based configuration

**After:**
```python
# apps/config/common.py
class Config:              # Base config
class DevelopmentConfig:   # Development
class ProductionConfig:    # Production
class TestConfig:          # Testing

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'test': TestConfig,
}
```

### 3. **Application Factory Pattern**

**Before:**
```python
# Direct app creation
app = Flask(__name__)
```

**After:**
```python
# apps/app.py
def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    # ...
    return app
```

### 4. **Centralized Extensions**

**Before:**
```python
# app/extensions.py
db = SQLAlchemy()
```

**After:**
```python
# apps/config/server.py
db = SQLAlchemy()
migrate = Migrate()
cors = CORS()
jwt = JWTManager()
```

## Module Structure Pattern

Each module follows this pattern:

```python
module_name/
├── __init__.py       # Module initialization
├── models.py         # Database models
├── views.py          # Route handlers (Blueprint)
├── utils.py          # Helper functions (optional)
└── forms.py          # Form validators (optional)
```

### Example: Auth Module

```python
# apps/auth/models.py
class User(db.Model):
    # User model definition

# apps/auth/views.py
from flask import Blueprint
bp = Blueprint("auth", __name__)

@bp.route("/login", methods=["POST"])
def login():
    # Login logic

# apps/auth/utils.py
def token_provider(user_id):
    # Generate JWT tokens
```

## Configuration

### Development
```python
from apps.app import create_app

app = create_app('development')
app.run(debug=True)
```

### Production
```python
from apps.app import create_app

app = create_app('production')
# Use production WSGI server (gunicorn, uwsgi)
```

### Testing
```python
from apps.app import create_app

app = create_app('test')
# Run tests
```

## Blueprint Registration

Blueprints are automatically registered in `apps/app.py`:

```python
def register_blueprints(app):
    from apps.auth.views import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix="/auth")
    
    from apps.post.views import bp as post_bp
    app.register_blueprint(post_bp, url_prefix="/post")
    # ...
```

## Database Models

Models are now distributed across modules but share the same `db` instance:

```python
# apps/auth/models.py
from apps.config.server import db

class User(db.Model):
    __tablename__ = "users"
    # ...

# apps/post/models.py
from apps.config.server import db
from apps.auth.models import User

class Post(db.Model):
    __tablename__ = "posts"
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    # ...
```

## Migration from Legacy Code

### Step 1: Copy Configuration
- ✅ `app/config.py` → `apps/config/common.py`
- ✅ `app/extensions.py` → `apps/config/server.py`

### Step 2: Copy JWT Handlers
- ✅ `app/jwt_handlers.py` → `apps/common/jwt_handlers.py`

### Step 3: Migrate Models
- ✅ `app/models/user.py` → `apps/auth/models.py`
- ⏳ `app/models/post.py` → `apps/post/models.py` (TODO)
- ⏳ `app/models/*.py` → respective modules (TODO)

### Step 4: Migrate Blueprints
- ✅ `app/blueprints/auth.py` → `apps/auth/views.py` (skeleton)
- ⏳ Other blueprints (TODO)

### Step 5: Migrate Utilities
- ✅ `app/utils/user_utils.py` → `apps/auth/utils.py`
- ⏳ Other utilities (TODO)

## Next Steps

1. **Complete Auth Module** - Implement full auth logic from legacy
2. **Migrate Post Module** - Copy models, views, utilities
3. **Migrate Reply Module** - Comments and nested replies
4. **Migrate User Module** - Follow/Friend relationships
5. **Migrate Route Module** - Navigation and paths
6. **Migrate Detector Module** - AI detection services
7. **Add Image Utilities** - Image upload, compression, storage
8. **Add Tests** - Unit and integration tests
9. **Update Documentation** - API documentation

## Benefits of New Structure

1. **Modularity** - Each module is self-contained
2. **Scalability** - Easy to add new modules
3. **Maintainability** - Clear separation of concerns
4. **Testability** - Modules can be tested independently
5. **Configuration** - Environment-based config management
6. **Reusability** - Shared utilities in common module

## Running the Application

```bash
# Development
python apps/app.py

# Production (with gunicorn)
gunicorn "apps.app:create_app('production')" --bind 0.0.0.0:8000

# Testing
pytest
```

## Legacy Compatibility

The refactored code maintains compatibility with:
- Same database schema
- Same API endpoints
- Same JWT authentication
- Same models and relationships

The migration can be done incrementally, with both structures coexisting during transition.
