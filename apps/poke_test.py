from apps.app import create_app

app = create_app('development')

HELP_TEXT = """\
Run this script to invoke schedule_osrm_customize() inside the Flask app context:
    python apps/poke_test.py
Ensure the development configuration is set before execution so schedule_osrm_customize has the right resources.
"""

print(HELP_TEXT)

with app.app_context():
    from apps.route.views import schedule_osrm_customize
    ok = schedule_osrm_customize()
    print("schedule_osrm_customize() ->", ok)
