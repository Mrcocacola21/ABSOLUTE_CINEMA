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


def test_openapi_describes_demo_auth_booking_and_profile_flows() -> None:
    app = create_application()
    spec = app.openapi()

    register = spec["paths"]["/api/v1/auth/register"]["post"]
    login = spec["paths"]["/api/v1/auth/login"]["post"]
    profile_update = spec["paths"]["/api/v1/users/me"]["patch"]
    profile_deactivate = spec["paths"]["/api/v1/users/me"]["delete"]
    ticket_purchase = spec["paths"]["/api/v1/tickets/purchase"]["post"]
    ticket_cancel = spec["paths"]["/api/v1/tickets/{ticket_id}/cancel"]["patch"]
    order_purchase = spec["paths"]["/api/v1/orders/purchase"]["post"]
    my_orders = spec["paths"]["/api/v1/users/me/orders"]["get"]

    assert register["summary"] == "Register a new user"
    assert "clients cannot self-register as administrators" in register["description"]
    assert login["summary"] == "Log in and receive a JWT"
    assert "form-encoded credentials" in login["description"]

    assert profile_update["security"] == [{"OAuth2PasswordBearer": []}]
    assert "role and activation flags cannot be changed" in profile_update["description"]
    assert profile_deactivate["security"] == [{"OAuth2PasswordBearer": []}]
    assert "Existing tokens stop working" in profile_deactivate["description"]

    assert ticket_purchase["security"] == [{"OAuth2PasswordBearer": []}]
    assert "exactly one specific seat" in ticket_purchase["description"]
    assert ticket_cancel["security"] == [{"OAuth2PasswordBearer": []}]
    assert "before the linked session starts" in ticket_cancel["description"]
    assert order_purchase["security"] == [{"OAuth2PasswordBearer": []}]
    assert "one or more specific seats" in order_purchase["description"]
    assert my_orders["security"] == [{"OAuth2PasswordBearer": []}]

    ticket_schema = spec["components"]["schemas"]["TicketPurchaseRequest"]
    order_schema = spec["components"]["schemas"]["OrderPurchaseRequest"]
    assert ticket_schema["additionalProperties"] is False
    assert ticket_schema["properties"]["seat_row"]["description"].startswith("One-based seat row")
    assert order_schema["additionalProperties"] is False
    assert "Unique seat coordinates" in order_schema["properties"]["seats"]["description"]
