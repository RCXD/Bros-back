import pytest
from flask_jwt_extended import create_access_token

from apps.app import create_app
from apps.auth.models import User
from apps.config.server import db


@pytest.fixture
def app():
    from apps.config import common

    # Use in-memory SQLite for isolated tests
    common.Config.SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    common.DevelopmentConfig.SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    common.TestConfig.SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

    app = create_app("test")
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_ECHO"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _create_user(username, email):
    user = User(username=username, email=email, address="", nickname=username)
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def user(app):
    with app.app_context():
        return _create_user("tester", "tester@example.com")


def _auth_headers(app, user):
    with app.app_context():
        token = create_access_token(identity=str(user.user_id))
    return {"Authorization": f"Bearer {token}"}


def _create_place(client, headers, name="Home"):
    resp = client.post(
        "/place",
        json={
            "name": name,
            "lat": 37.5,
            "lon": 127.0,
            "point": 4.5,
            "radius": 50,
            "description": "Marker",
            "is_public": False,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.get_json()["place"]


def test_create_and_retrieve_place(client, app, user):
    headers = _auth_headers(app, user)
    created = _create_place(client, headers)

    list_resp = client.get("/place", headers=headers)
    assert list_resp.status_code == 200
    list_data = list_resp.get_json()
    assert list_data["total"] == 1
    assert list_data["items"][0]["place_id"] == created["place_id"]

    get_resp = client.get(f"/place/{created['place_id']}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.get_json()["place"]["name"] == "Home"


def test_update_and_delete_requires_owner(client, app, user):
    headers = _auth_headers(app, user)
    created = _create_place(client, headers)

    with app.app_context():
        other_user = _create_user("other", "other@example.com")
    other_headers = _auth_headers(app, other_user)

    forbidden_update = client.put(
        f"/place/{created['place_id']}",
        json={"name": "Nope"},
        headers=other_headers,
    )
    assert forbidden_update.status_code == 403

    forbidden_delete = client.delete(
        f"/place/{created['place_id']}", headers=other_headers
    )
    assert forbidden_delete.status_code == 403

    update_resp = client.put(
        f"/place/{created['place_id']}",
        json={"name": "Updated", "point": 3},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.get_json()["place"]["name"] == "Updated"

    delete_resp = client.delete(f"/place/{created['place_id']}", headers=headers)
    assert delete_resp.status_code == 200

    missing_resp = client.get(f"/place/{created['place_id']}", headers=headers)
    assert missing_resp.status_code == 404


def test_validation_errors(client, app, user):
    headers = _auth_headers(app, user)

    missing_name = client.post(
        "/place", json={"lat": 10, "lon": 10}, headers=headers
    )
    assert missing_name.status_code == 400

    invalid_lat = client.post(
        "/place",
        json={"name": "Bad", "lat": 200, "lon": 10},
        headers=headers,
    )
    assert invalid_lat.status_code == 400

    invalid_point = client.post(
        "/place",
        json={"name": "Bad", "lat": 10, "lon": 10, "point": 6},
        headers=headers,
    )
    assert invalid_point.status_code == 400

    invalid_radius = client.post(
        "/place",
        json={"name": "Bad", "lat": 10, "lon": 10, "radius": "abc"},
        headers=headers,
    )
    assert invalid_radius.status_code == 400


def test_auth_required(client):
    resp = client.get("/place")
    assert resp.status_code == 401
