from apps.app import create_app

app = create_app('development')

with app.app_context():
    from apps.route.views import schedule_osrm_customize
    ok = schedule_osrm_customize()
    print("schedule_osrm_customize() ->", ok)
