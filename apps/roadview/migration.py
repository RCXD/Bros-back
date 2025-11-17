"""
Database Migration for Roadview Models

Run this migration to create the roadview tables:
    flask db migrate -m "Add roadview models"
    flask db upgrade

Or use this SQL directly if not using Flask-Migrate
"""

# PostgreSQL/MySQL Migration SQL

CREATE_ROADVIEWS_TABLE = """
CREATE TABLE roadviews (
    roadview_id SERIAL PRIMARY KEY,
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    address VARCHAR(500),
    provider VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    pano_id VARCHAR(255),
    heading FLOAT,
    pitch FLOAT,
    fov FLOAT DEFAULT 90.0,
    zoom INTEGER DEFAULT 1,
    thumbnail_url VARCHAR(1000),
    panorama_url VARCHAR(1000),
    image_width INTEGER,
    image_height INTEGER,
    provider_data JSONB,
    image_date DATE,
    distance_from_location FLOAT,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    user_id INTEGER REFERENCES users(user_id),
    location_id INTEGER REFERENCES locations(location_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);

CREATE INDEX idx_roadviews_latitude ON roadviews(latitude);
CREATE INDEX idx_roadviews_longitude ON roadviews(longitude);
CREATE INDEX idx_roadviews_provider ON roadviews(provider);
CREATE INDEX idx_roadviews_created_at ON roadviews(created_at DESC);
"""

CREATE_ROADVIEW_CACHE_TABLE = """
CREATE TABLE roadview_cache (
    cache_id SERIAL PRIMARY KEY,
    lat_rounded FLOAT NOT NULL,
    lng_rounded FLOAT NOT NULL,
    google_available BOOLEAN,
    kakao_available BOOLEAN,
    naver_available BOOLEAN,
    best_provider VARCHAR(50),
    check_count INTEGER DEFAULT 1,
    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_location_cache ON roadview_cache(lat_rounded, lng_rounded);
"""

CREATE_ROADVIEW_REQUESTS_TABLE = """
CREATE TABLE roadview_requests (
    request_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    preferred_provider VARCHAR(50),
    providers_checked JSONB,
    provider_used VARCHAR(50),
    roadview_id INTEGER REFERENCES roadviews(roadview_id),
    response_time_ms INTEGER,
    api_calls_made INTEGER DEFAULT 0,
    cache_hit BOOLEAN DEFAULT FALSE,
    success BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_roadview_requests_user_id ON roadview_requests(user_id);
CREATE INDEX idx_roadview_requests_created_at ON roadview_requests(created_at DESC);
"""

CREATE_ROADVIEW_API_USAGE_TABLE = """
CREATE TABLE roadview_api_usage (
    usage_id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,
    date DATE NOT NULL,
    total_requests INTEGER DEFAULT 0,
    successful_requests INTEGER DEFAULT 0,
    failed_requests INTEGER DEFAULT 0,
    cached_requests INTEGER DEFAULT 0,
    estimated_cost FLOAT DEFAULT 0.0,
    daily_limit INTEGER,
    quota_exceeded BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(provider, date)
);

CREATE INDEX idx_roadview_api_usage_date ON roadview_api_usage(date DESC);
"""

# SQLite Version (for development)
CREATE_ROADVIEWS_TABLE_SQLITE = """
CREATE TABLE roadviews (
    roadview_id INTEGER PRIMARY KEY AUTOINCREMENT,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    address VARCHAR(500),
    provider VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    pano_id VARCHAR(255),
    heading REAL,
    pitch REAL,
    fov REAL DEFAULT 90.0,
    zoom INTEGER DEFAULT 1,
    thumbnail_url VARCHAR(1000),
    panorama_url VARCHAR(1000),
    image_width INTEGER,
    image_height INTEGER,
    provider_data TEXT,
    image_date DATE,
    distance_from_location REAL,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    user_id INTEGER,
    location_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (location_id) REFERENCES locations(location_id)
);

CREATE INDEX idx_roadviews_latitude ON roadviews(latitude);
CREATE INDEX idx_roadviews_longitude ON roadviews(longitude);
"""

# Sample Data
SAMPLE_DATA = """
-- Sample roadview record (Google)
INSERT INTO roadviews (latitude, longitude, provider, status, pano_id, heading, pitch, user_id)
VALUES (37.5665, 126.9780, 'google_street_view', 'available', 'CAoSLEFGMVFpcE...', 90.0, 0.0, 1);

-- Sample cache entry
INSERT INTO roadview_cache (lat_rounded, lng_rounded, google_available, kakao_available, best_provider)
VALUES (37.567, 126.978, true, true, 'google_street_view');

-- Sample API usage
INSERT INTO roadview_api_usage (provider, date, total_requests, successful_requests)
VALUES ('google_street_view', CURRENT_DATE, 150, 130);
"""


def upgrade_database(db_engine):
    """
    Upgrade database with roadview tables
    
    Args:
        db_engine: SQLAlchemy engine instance
    """
    with db_engine.connect() as conn:
        conn.execute(CREATE_ROADVIEWS_TABLE)
        conn.execute(CREATE_ROADVIEW_CACHE_TABLE)
        conn.execute(CREATE_ROADVIEW_REQUESTS_TABLE)
        conn.execute(CREATE_ROADVIEW_API_USAGE_TABLE)
        conn.commit()


def downgrade_database(db_engine):
    """
    Remove roadview tables
    
    Args:
        db_engine: SQLAlchemy engine instance
    """
    with db_engine.connect() as conn:
        conn.execute("DROP TABLE IF EXISTS roadview_api_usage CASCADE;")
        conn.execute("DROP TABLE IF EXISTS roadview_requests CASCADE;")
        conn.execute("DROP TABLE IF EXISTS roadview_cache CASCADE;")
        conn.execute("DROP TABLE IF EXISTS roadviews CASCADE;")
        conn.commit()


if __name__ == "__main__":
    print("Roadview Database Migration SQL")
    print("=" * 60)
    print("\nCreate Roadviews Table:")
    print(CREATE_ROADVIEWS_TABLE)
    print("\nCreate Cache Table:")
    print(CREATE_ROADVIEW_CACHE_TABLE)
    print("\nCreate Requests Table:")
    print(CREATE_ROADVIEW_REQUESTS_TABLE)
    print("\nCreate API Usage Table:")
    print(CREATE_ROADVIEW_API_USAGE_TABLE)
