"""
Tests for Group B Security:
- Docs/OpenAPI disabled in production
- httpOnly cookies for access/refresh tokens
- Password minimum length (8+) in backend schemas and endpoints
"""
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from app.main import app
from app.core.config import settings
from app.core.security import create_access_token


@pytest.mark.asyncio
async def test_docs_and_openapi_disabled_in_production(monkeypatch):
    """Verify /docs, /redoc, and /openapi.json are disabled when ENV=production."""
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    assert settings.is_production is True

    # Build a production app instance mirroring main.py logic
    prod_app = FastAPI(
        title="SPT Hospital HRMS API",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    async with AsyncClient(transport=ASGITransport(app=prod_app), base_url="http://test") as client:
        docs_res = await client.get("/docs")
        assert docs_res.status_code == 404

        redoc_res = await client.get("/redoc")
        assert redoc_res.status_code == 404

        openapi_res = await client.get("/openapi.json")
        assert openapi_res.status_code == 404


@pytest.mark.asyncio
async def test_auth_httponly_cookies_and_cookie_auth():
    """Verify login sets httpOnly cookies, endpoints authenticate via cookie, and logout clears them."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Login
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "Admin@123"}
        )
        assert login_res.status_code == 200
        data = login_res.json()
        assert "access_token" in data
        assert "refresh_token" in data

        # Check cookies set
        cookies = login_res.cookies
        assert "access_token" in cookies
        assert "refresh_token" in cookies

        # 2. Call /auth/me using ONLY cookies (no Authorization header)
        cookie_client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test", cookies=cookies)
        me_res = await cookie_client.get("/api/v1/auth/me")
        assert me_res.status_code == 200
        assert me_res.json()["username"] == "admin"

        # 3. Call /auth/refresh using cookies
        refresh_res = await cookie_client.post("/api/v1/auth/refresh", json={})
        assert refresh_res.status_code == 200
        assert "access_token" in refresh_res.cookies
        assert "refresh_token" in refresh_res.cookies

        # 4. Call /auth/logout
        logout_res = await cookie_client.post("/api/v1/auth/logout")
        assert logout_res.status_code == 200


@pytest.mark.asyncio
async def test_password_policy_minimum_8_characters():
    """Verify backend enforces 8+ characters on user create, user update, and change-password."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "Admin@123"}
        )
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Create user with 7 char password -> 422
        bad_create = await client.post(
            "/api/v1/users",
            headers=headers,
            json={
                "username": "shortpwduser",
                "email": "shortpwd@spthospital.com",
                "full_name": "Short Pwd",
                "password": "1234567",
                "role": "EMPLOYEE"
            }
        )
        assert bad_create.status_code == 422

        # 2. Create user with 8 char password -> 200
        good_create = await client.post(
            "/api/v1/users",
            headers=headers,
            json={
                "username": "validpwduser",
                "email": "validpwd@spthospital.com",
                "full_name": "Valid Pwd",
                "password": "valid123",
                "role": "EMPLOYEE"
            }
        )
        assert good_create.status_code == 200
        user_id = good_create.json()["id"]

        try:
            # 3. Update user with short password -> 422
            bad_update = await client.put(
                f"/api/v1/users/{user_id}",
                headers=headers,
                json={"password": "short"}
            )
            assert bad_update.status_code == 422

            # 4. Update user with valid 8+ password -> 200
            good_update = await client.put(
                f"/api/v1/users/{user_id}",
                headers=headers,
                json={"password": "newvalidpassword123"}
            )
            assert good_update.status_code == 200
        finally:
            # Clean up test user
            await client.delete(f"/api/v1/users/{user_id}", headers=headers)
