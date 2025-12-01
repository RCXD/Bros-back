"""List all registered routes in the Flask app"""

from apps.app import create_app
import os

app = create_app("development")

print("Registered Routes:")
print("=" * 80)

routes = []
for rule in app.url_map.iter_rules():
    routes.append(
        {
            "endpoint": rule.endpoint,
            "methods": ",".join(sorted(rule.methods - {"HEAD", "OPTIONS"})),
            "path": str(rule),
        }
    )

# Sort by path
routes.sort(key=lambda x: x["path"])

# Filter route module
route_routes = [r for r in routes if "/route" in r["path"]]

print("\nRoute module endpoints:")
for route in route_routes:
    print(f"  {route['methods']:8} {route['path']}")

print(f"\nTotal /route endpoints: {len(route_routes)}")

# Check if analyze exists
analyze_routes = [r for r in routes if "analyze" in r["path"].lower()]
if analyze_routes:
    print("\nAnalyze endpoints found:")
    for route in analyze_routes:
        print(f"  {route['methods']:8} {route['path']}")
else:
    print("\n❌ No 'analyze' endpoints found!")
