from apps.app import create_app

app = create_app('development')

print("\n=== Post Blueprint Routes ===")
for rule in app.url_map.iter_rules():
    if 'post' in rule.rule and 'image' in rule.rule:
        print(f"{rule.methods} {rule.rule}")

print("\n=== All Post Routes ===")
for rule in app.url_map.iter_rules():
    if rule.endpoint and rule.endpoint.startswith('post'):
        print(f"{rule.methods} {rule.rule} -> {rule.endpoint}")
