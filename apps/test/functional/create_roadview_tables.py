"""
Create roadview database tables
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from apps.app import create_app
from apps.config.server import db
from apps.roadview.views import init_roadview_models

app = create_app()

with app.app_context():
    # Models are already initialized in create_app()
    # Just create tables
    db.create_all()

    print("✓ Roadview tables created successfully!")
    print("Tables:")
    print("  - roadviews")
    print("  - roadview_cache")
    print("  - roadview_requests")
    print("  - roadview_api_usage")
