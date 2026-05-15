"""
Pytest unit tests for the authentication endpoints.

Covers:
    POST   /auth/user          – signup
    POST   /auth/login         – login (credentials & OAuth paths)
    GET    /auth/me            – get current user
    PUT    /auth/user          – update profile
    DELETE /auth/logout        – logout (token blacklist)
    DELETE /auth/user          – account deletion
    POST   /auth/refresh       – token refresh
    POST   /auth/login/google  – deprecated Google OAuth shim
    POST   /auth/login/kakao   – deprecated Kakao OAuth shim
    POST   /auth/login/naver   – deprecated Naver OAuth shim
    GET    /auth/api_info      – developer info endpoint
"""

import json
from unittest.mock import patch, MagicMock

import pytest


# ===========================================================================
# Helpers
# ===========================================================================


def _signup(client, username="user1", password="Pass1234!", email="u1@test.com"):
    """POST /auth/user with sensible defaults.

    Args:
        client: Flask test client.
        username: Account username.
        password: Account password.
        email: Account email.

    Returns:
        Flask Response object.
    """
    return client.post(
        "/auth/user",
        data={"username": username, "password": password, "email": email},
    )


def _login(client, username="user1", password="Pass1234!"):
    """POST /auth/login with username/password.

    Args:
        client: Flask test client.
        username: Account username.
        password: Account password.

    Returns:
        Flask Response object.
    """
    return client.post(
        "/auth/login",
        json={"username": username, "password": password},
    )


# ===========================================================================
# POST /auth/user  –  signup
# ===========================================================================


class TestSignup:
    """Tests for the user registration endpoint."""

    def test_signup_success(self, client):
        """Happy-path: valid data returns 201 with user_id."""
        resp = _signup(client)
        assert resp.status_code == 201
        data = resp.get_json()
        assert "user" in data
        assert "user_id" in data["user"]

    def test_signup_missing_username(self, client):
        """Missing required field returns 400."""
        resp = client.post(
            "/auth/user", data={"password": "Pass1234!", "email": "x@test.com"}
        )
        assert resp.status_code == 400

    def test_signup_missing_password(self, client):
        """Missing password returns 400."""
        resp = client.post(
            "/auth/user", data={"username": "bob", "email": "bob@test.com"}
        )
        assert resp.status_code == 400

    def test_signup_missing_email(self, client):
        """Missing email returns 400."""
        resp = client.post(
            "/auth/user", data={"username": "bob", "password": "Pass1234!"}
        )
        assert resp.status_code == 400

    def test_signup_invalid_email(self, client):
        """Invalid e-mail format returns 400."""
        resp = client.post(
            "/auth/user",
            data={"username": "bob", "password": "Pass1234!", "email": "not-an-email"},
        )
        assert resp.status_code == 400

    def test_signup_duplicate_username(self, client):
        """Registering the same username twice returns 409."""
        _signup(client)
        resp = _signup(client, email="other@test.com")
        assert resp.status_code == 409
        assert "사용자명" in resp.get_json()["message"]

    def test_signup_duplicate_email(self, client):
        """Registering the same e-mail twice returns 409."""
        _signup(client)
        resp = _signup(client, username="user2")
        assert resp.status_code == 409
        assert "이메일" in resp.get_json()["message"]

    def test_signup_invalid_phone(self, client):
        """Invalid phone number format returns 400."""
        resp = client.post(
            "/auth/user",
            data={
                "username": "bob",
                "password": "Pass1234!",
                "email": "bob@test.com",
                "phone": "invalid-phone",
            },
        )
        assert resp.status_code == 400

    def test_signup_valid_phone(self, client):
        """Valid Korean phone number is accepted."""
        resp = client.post(
            "/auth/user",
            data={
                "username": "bob",
                "password": "Pass1234!",
                "email": "bob@test.com",
                "phone": "010-1234-5678",
            },
        )
        assert resp.status_code == 201


# ===========================================================================
# POST /auth/login  –  credential login
# ===========================================================================


class TestLogin:
    """Tests for the unified login endpoint (credentials path)."""

    def test_login_success(self, client):
        """Correct credentials return 200 with access_token."""
        _signup(client)
        with patch("apps.auth.utils.get_medal_summary", return_value={}), patch(
            "apps.auth.utils.get_user_league_info",
            return_value={"enabled": False, "league": {}},
        ):
            resp = _login(client)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert "user_data" in data

    def test_login_wrong_password(self, client):
        """Wrong password returns 401."""
        _signup(client)
        resp = client.post(
            "/auth/login", json={"username": "user1", "password": "WrongPass!"}
        )
        assert resp.status_code == 401

    def test_login_unknown_user(self, client):
        """Unknown username returns 401."""
        resp = client.post(
            "/auth/login",
            json={"username": "nobody", "password": "Pass1234!"},
        )
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        """Missing both username and password returns 400."""
        resp = client.post("/auth/login", json={})
        assert resp.status_code == 400

    def test_login_suspended_account(self, client, app):
        """A suspended (is_expired=True) account returns 403."""
        _signup(client)
        with app.app_context():
            from apps.auth.models import User

            user = User.query.filter_by(username="user1").first()
            user.is_expired = True
            from apps.config.server import db

            db.session.commit()
        resp = _login(client)
        assert resp.status_code == 403


# ===========================================================================
# POST /auth/login  –  OAuth path
# ===========================================================================


class TestOAuthLogin:
    """Tests for the OAuth login flow via POST /auth/login."""

    def _mock_verify(self, oauth_type, username, email, nickname):
        """Build a mock for ``verify_oauth_token`` returning success.

        Args:
            oauth_type: An :class:`~apps.auth.models.OauthType` value.
            username: Social user-id string.
            email: User e-mail.
            nickname: Display name.

        Returns:
            A tuple matching the verify_oauth_token return signature.
        """
        return (oauth_type, username, email, nickname, None)

    def test_oauth_missing_token(self, client):
        """Provider supplied but token missing returns 400."""
        resp = client.post("/auth/login", json={"provider": "google"})
        assert resp.status_code == 400

    def test_oauth_invalid_token(self, client):
        """Invalid OAuth token returns 401."""
        with patch(
            "apps.auth.views.verify_oauth_token", return_value=(None, "Invalid token")
        ):
            resp = client.post(
                "/auth/login", json={"provider": "google", "token": "bad-token"}
            )
        assert resp.status_code == 401

    def test_oauth_google_success(self, client, app):
        """Valid Google token creates/finds user and returns 200 with tokens."""
        from apps.auth.models import OauthType

        with patch(
            "apps.auth.views.verify_oauth_token",
            return_value=self._mock_verify(
                OauthType.GOOGLE, "google_123", "guser@gmail.com", "GUser"
            ),
        ), patch(
            "apps.auth.utils.get_medal_summary", return_value={}
        ), patch(
            "apps.auth.utils.get_user_league_info",
            return_value={"enabled": False, "league": {}},
        ):
            resp = client.post(
                "/auth/login", json={"provider": "google", "token": "valid-google-tok"}
            )
        assert resp.status_code == 200
        assert "access_token" in resp.get_json()

    def test_oauth_unsupported_provider(self, client):
        """Unsupported provider name returns 401."""
        with patch(
            "apps.auth.views.verify_oauth_token",
            return_value=(None, "지원하지 않는 OAuth 제공자입니다: foobar"),
        ):
            resp = client.post(
                "/auth/login", json={"provider": "foobar", "token": "tok"}
            )
        assert resp.status_code == 401


# ===========================================================================
# GET /auth/me
# ===========================================================================


class TestGetMe:
    """Tests for the current-user information endpoint."""

    def test_get_me_success(self, client, registered_user, auth_headers):
        """Authenticated request returns 200 with user_id."""
        resp = client.get("/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["user_id"] == registered_user["user_id"]
        assert data["username"] == registered_user["username"]

    def test_get_me_no_token(self, client):
        """Unauthenticated request returns 401."""
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_get_me_invalid_token(self, client):
        """Malformed bearer token returns 401."""
        resp = client.get("/auth/me", headers={"Authorization": "Bearer bad.token"})
        assert resp.status_code == 401


# ===========================================================================
# PUT /auth/user  –  profile update
# ===========================================================================


class TestUpdateProfile:
    """Tests for the profile update endpoint."""

    def test_update_nickname(self, client, registered_user, auth_headers):
        """Updating nickname returns 200 and reflects the change."""
        resp = client.put(
            "/auth/user", data={"nickname": "NewNick"}, headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["user"]["nickname"] == "NewNick"

    def test_update_email_success(self, client, registered_user, auth_headers):
        """Updating to a new valid e-mail returns 200."""
        resp = client.put(
            "/auth/user",
            data={"email": "newmail@example.com"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["user"]["email"] == "newmail@example.com"

    def test_update_email_invalid(self, client, registered_user, auth_headers):
        """Updating to an invalid e-mail format returns 400."""
        resp = client.put(
            "/auth/user", data={"email": "not-valid"}, headers=auth_headers
        )
        assert resp.status_code == 400

    def test_update_no_token(self, client):
        """Unauthenticated profile update returns 401."""
        resp = client.put("/auth/user", data={"nickname": "X"})
        assert resp.status_code == 401

    def test_update_invalid_phone(self, client, registered_user, auth_headers):
        """Updating to an invalid phone number returns 400."""
        resp = client.put(
            "/auth/user", data={"phone": "0000"}, headers=auth_headers
        )
        assert resp.status_code == 400


# ===========================================================================
# DELETE /auth/logout
# ===========================================================================


class TestLogout:
    """Tests for the logout endpoint."""

    def test_logout_success(self, client, registered_user, auth_headers):
        """Authenticated logout returns 200."""
        resp = client.delete("/auth/logout", headers=auth_headers)
        assert resp.status_code == 200
        assert "로그아웃" in resp.get_json()["message"]

    def test_logout_no_token(self, client):
        """Unauthenticated logout returns 401."""
        resp = client.delete("/auth/logout")
        assert resp.status_code == 401

    def test_token_blacklisted_after_logout(self, client, registered_user, auth_headers):
        """After logout the same token is rejected on subsequent requests."""
        client.delete("/auth/logout", headers=auth_headers)
        resp = client.get("/auth/me", headers=auth_headers)
        assert resp.status_code == 401


# ===========================================================================
# DELETE /auth/user  –  account deletion
# ===========================================================================


class TestRemoveAccount:
    """Tests for the account deletion endpoint."""

    def test_remove_account_success(self, client, registered_user, auth_headers, app):
        """Authenticated account deletion returns 200 and removes the user."""
        resp = client.delete("/auth/user", headers=auth_headers)
        assert resp.status_code == 200
        with app.app_context():
            from apps.auth.models import User

            user = User.query.get(registered_user["user_id"])
            assert user is None

    def test_remove_account_no_token(self, client):
        """Unauthenticated deletion returns 401."""
        resp = client.delete("/auth/user")
        assert resp.status_code == 401


# ===========================================================================
# POST /auth/refresh
# ===========================================================================


class TestRefresh:
    """Tests for the token refresh endpoint."""

    def test_refresh_success(self, client, registered_user, refresh_headers):
        """A valid refresh token returns a new access_token."""
        resp = client.post("/auth/refresh", headers=refresh_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data

    def test_refresh_with_access_token_fails(self, client, registered_user, auth_headers):
        """Sending an access token to the refresh endpoint returns 422."""
        resp = client.post("/auth/refresh", headers=auth_headers)
        assert resp.status_code == 422

    def test_refresh_no_token(self, client):
        """Missing token returns 401."""
        resp = client.post("/auth/refresh")
        assert resp.status_code == 401


# ===========================================================================
# Deprecated OAuth shim endpoints
# ===========================================================================


class TestDeprecatedOAuthEndpoints:
    """Tests for the deprecated per-provider OAuth shim routes."""

    def _mock_success(self, oauth_type_val, provider):
        """Patch verify_oauth_token with a successful return.

        Args:
            oauth_type_val: OauthType enum value to return.
            provider: Provider string used in the URL path.

        Returns:
            Tuple representing a successful oauth verification result.
        """
        return (
            oauth_type_val,
            f"{provider}_uid_999",
            f"{provider}_user@test.com",
            f"{provider.capitalize()}User",
            None,
        )

    def test_google_shim_missing_token(self, client):
        """Missing token in deprecated Google endpoint returns 400."""
        resp = client.post("/auth/login/google", json={})
        assert resp.status_code == 400

    def test_google_shim_invalid_token(self, client):
        """Invalid token in deprecated Google endpoint returns 401."""
        with patch(
            "apps.auth.views.verify_oauth_token",
            return_value=(None, "Invalid"),
        ):
            resp = client.post("/auth/login/google", json={"token": "bad"})
        assert resp.status_code == 401

    def test_google_shim_success(self, client):
        """Valid token in deprecated Google endpoint returns 200."""
        from apps.auth.models import OauthType

        with patch(
            "apps.auth.views.verify_oauth_token",
            return_value=self._mock_success(OauthType.GOOGLE, "google"),
        ), patch("apps.auth.utils.get_medal_summary", return_value={}), patch(
            "apps.auth.utils.get_user_league_info",
            return_value={"enabled": False, "league": {}},
        ):
            resp = client.post("/auth/login/google", json={"token": "valid"})
        assert resp.status_code == 200

    def test_kakao_shim_missing_token(self, client):
        """Missing token in deprecated Kakao endpoint returns 400."""
        resp = client.post("/auth/login/kakao", json={})
        assert resp.status_code == 400

    def test_naver_shim_missing_token(self, client):
        """Missing token in deprecated Naver endpoint returns 400."""
        resp = client.post("/auth/login/naver", json={})
        assert resp.status_code == 400


# ===========================================================================
# GET /auth/api_info
# ===========================================================================


class TestApiInfo:
    """Tests for the development API info endpoint."""

    def test_api_info_returns_200(self, client):
        """api_info endpoint is accessible without authentication."""
        resp = client.get("/auth/api_info")
        assert resp.status_code == 200

    def test_api_info_contains_module(self, client):
        """Response body contains module metadata."""
        data = client.get("/auth/api_info").get_json()
        assert data.get("module") == "auth"
        assert "endpoints" in data
        assert isinstance(data["endpoints"], list)
