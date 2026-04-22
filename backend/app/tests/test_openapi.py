"""Regression tests for the OpenAPI surface exposed in Swagger."""

from __future__ import annotations

from app.main import create_application


def test_openapi_metadata_includes_demo_ready_tags_and_contact() -> None:
    app = create_application()
    spec = app.openapi()

    assert spec["info"]["title"] == "Cinema Showcase API"
    assert "one-hall cinema" in spec["info"]["description"]
    assert spec["info"]["contact"]["url"].endswith("ABSOLUTE_CINEMA")

    tag_names = [tag["name"] for tag in spec["tags"]]
    assert tag_names == [
        "health",
        "auth",
        "users",
        "movies",
        "schedule",
        "sessions",
        "orders",
        "tickets",
        "admin",
    ]


def test_openapi_uses_swagger_token_exchange_for_authorize_flow() -> None:
    app = create_application()
    spec = app.openapi()

    security_schemes = spec["components"]["securitySchemes"]
    scheme = security_schemes["OAuth2PasswordBearer"]

    assert scheme["type"] == "oauth2"
    assert scheme["flows"]["password"]["tokenUrl"] == "/api/v1/auth/token"
    assert "/api/v1/auth/token" not in spec["paths"]


def test_openapi_marks_protected_routes_and_error_contracts() -> None:
    app = create_application()
    spec = app.openapi()

    users_me = spec["paths"]["/api/v1/users/me"]["get"]
    admin_movies = spec["paths"]["/api/v1/admin/movies"]["get"]
    public_movies = spec["paths"]["/api/v1/movies"]["get"]
    schedule = spec["paths"]["/api/v1/schedule"]["get"]

    assert users_me["security"] == [{"OAuth2PasswordBearer": []}]
    assert "401" in users_me["responses"]

    assert admin_movies["security"] == [{"OAuth2PasswordBearer": []}]
    assert "401" in admin_movies["responses"]
    assert "403" in admin_movies["responses"]

    assert public_movies["summary"] == "Browse movies"
    assert "422" in public_movies["responses"]

    assert schedule["summary"] == "Browse the public schedule"
    assert "422" in schedule["responses"]
