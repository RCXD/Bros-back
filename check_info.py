import json

with open("apps/route/info.json", encoding="utf-8") as f:
    data = json.load(f)
    endpoints = data.get("endpoints", [])
    print(f"✅ Valid JSON")
    print(f"Total endpoints: {len(endpoints)}")
    print("\nEndpoints:")
    for ep in endpoints:
        auth = "🔒" if ep.get("auth_required") else "🔓"
        print(f'  {auth} {ep.get("method", "?")} {ep.get("path", "?")}')
