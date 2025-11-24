"""
Directly create roadview tables in MySQL
"""

import pymysql

# Database connection
conn = pymysql.connect(
    host="192.168.1.79", user="user1", password="1234", database="404found_test2"
)

cursor = conn.cursor()

# Create tables
sqls = [
    # Roadviews table
    """
    CREATE TABLE IF NOT EXISTS roadviews (
        roadview_id INT AUTO_INCREMENT PRIMARY KEY,
        latitude FLOAT NOT NULL,
        longitude FLOAT NOT NULL,
        address VARCHAR(500),
        provider VARCHAR(50) NOT NULL,
        status VARCHAR(20) DEFAULT 'pending',
        pano_id VARCHAR(255),
        heading FLOAT,
        pitch FLOAT,
        fov FLOAT DEFAULT 90.0,
        zoom INT DEFAULT 1,
        thumbnail_url VARCHAR(1000),
        panorama_url VARCHAR(1000),
        image_width INT,
        image_height INT,
        provider_data JSON,
        image_date DATE,
        distance_from_location FLOAT,
        error_message TEXT,
        retry_count INT DEFAULT 0,
        user_id INT,
        location_id INT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        expires_at TIMESTAMP NULL,
        INDEX idx_roadviews_latitude (latitude),
        INDEX idx_roadviews_longitude (longitude),
        INDEX idx_roadviews_provider (provider),
        INDEX idx_roadviews_created_at (created_at DESC),
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    """,
    # Cache table
    """
    CREATE TABLE IF NOT EXISTS roadview_cache (
        cache_id INT AUTO_INCREMENT PRIMARY KEY,
        lat_rounded FLOAT NOT NULL,
        lng_rounded FLOAT NOT NULL,
        google_available BOOLEAN,
        kakao_available BOOLEAN,
        naver_available BOOLEAN,
        best_provider VARCHAR(50),
        check_count INT DEFAULT 1,
        last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_location_cache (lat_rounded, lng_rounded)
    )
    """,
    # Requests table
    """
    CREATE TABLE IF NOT EXISTS roadview_requests (
        request_id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        latitude FLOAT NOT NULL,
        longitude FLOAT NOT NULL,
        preferred_provider VARCHAR(50),
        providers_checked JSON,
        provider_used VARCHAR(50),
        roadview_id INT,
        response_time_ms INT,
        api_calls_made INT DEFAULT 0,
        cache_hit BOOLEAN DEFAULT FALSE,
        success BOOLEAN DEFAULT FALSE,
        error_message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_roadview_requests_user_id (user_id),
        INDEX idx_roadview_requests_created_at (created_at DESC),
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        FOREIGN KEY (roadview_id) REFERENCES roadviews(roadview_id)
    )
    """,
    # API Usage table
    """
    CREATE TABLE IF NOT EXISTS roadview_api_usage (
        usage_id INT AUTO_INCREMENT PRIMARY KEY,
        provider VARCHAR(50) NOT NULL,
        date DATE NOT NULL,
        total_requests INT DEFAULT 0,
        successful_requests INT DEFAULT 0,
        failed_requests INT DEFAULT 0,
        cached_requests INT DEFAULT 0,
        estimated_cost FLOAT DEFAULT 0.0,
        daily_limit INT,
        quota_exceeded BOOLEAN DEFAULT FALSE,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY unique_provider_date (provider, date),
        INDEX idx_roadview_api_usage_date (date DESC)
    )
    """,
]

try:
    for sql in sqls:
        print(f"Executing: {sql[:80]}...")
        cursor.execute(sql)
        print("  ✓ Success")

    conn.commit()
    print("\n✓ All roadview tables created successfully!")

    # Verify
    cursor.execute("SHOW TABLES LIKE 'roadview%'")
    tables = cursor.fetchall()
    print(f"\nCreated tables:")
    for table in tables:
        print(f"  - {table[0]}")

except Exception as e:
    print(f"❌ Error: {str(e)}")
    conn.rollback()
finally:
    cursor.close()
    conn.close()
