"""Shared OpenAPI and Swagger configuration for the Cinema Showcase API."""

from __future__ import annotations

from typing import Any

from fastapi import status

from app.core.responses import ErrorResponse

PROJECT_REPOSITORY_URL = "https://github.com/Mrcocacola21/ABSOLUTE_CINEMA"

OPENAPI_DESCRIPTION = """
Cinema Showcase is an academic FastAPI backend for a one-hall cinema. The API supports
public movie and schedule browsing, ticket and order purchase flows, authenticated user
profiles, and an administrator workspace for movie, session, and attendance management.

## Demo Workflow

1. Register a user with `POST /api/v1/auth/register`, or sign in with `POST /api/v1/auth/login`.
2. Use the **Authorize** button in Swagger UI to obtain a JWT automatically.
3. Restore the authenticated session with `GET /api/v1/users/me`.
4. Explore the public catalog with the `movies` and `schedule` tags.
5. Use the `admin` tag for protected management flows when signed in as an administrator.

## Localized Fields

Movie titles and descriptions are localized with two keys:

- `uk`: Ukrainian copy shown in the Ukrainian UI
- `en`: English copy shown in the English UI

Swagger examples use that structure consistently across movie and schedule responses.
""".strip()

API_TAGS: list[dict[str, str]] = [
    {
        "name": "health",
        "description": "Liveness checks used by Docker, deployment scripts, and local environment verification.",
    },
    {
        "name": "auth",
        "description": (
            "Registration and login flows. Swagger's **Authorize** button uses a dedicated OAuth2 "
            "token exchange behind the scenes, while `POST /auth/login` remains the app-facing login endpoint."
        ),
    },
    {
        "name": "users",
        "description": (
            "Authenticated profile and order-history endpoints that back the frontend `/profile` area."
        ),
    },
    {
        "name": "movies",
        "description": "Public movie catalog endpoints with localized movie metadata and lifecycle status.",
    },
    {
        "name": "schedule",
        "description": "Public schedule browsing endpoints for upcoming sessions, details, and filters.",
    },
    {
        "name": "sessions",
        "description": "Session-specific public utilities such as seat-map availability for a selected showing.",
    },
    {
        "name": "orders",
        "description": "Authenticated multi-seat booking and order-cancellation flows.",
    },
    {
        "name": "tickets",
        "description": "Authenticated single-ticket purchase, listing, and cancellation flows.",
    },
    {
        "name": "admin",
        "description": (
            "Protected administration endpoints behind the frontend `/admin` workspace, including "
            "movies, sessions, users, tickets, and attendance reporting."
        ),
    },
]

SWAGGER_UI_PARAMETERS = {
    "displayRequestDuration": True,
    "filter": True,
    "persistAuthorization": True,
    "tryItOutEnabled": True,
    "defaultModelsExpandDepth": 1,
    "docExpansion": "list",
}


def _build_error_example(
    *,
    code: str,
    message: str,
    details: Any | None = None,
) -> dict[str, Any]:
    error = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if details is not None:
        error["error"]["details"] = details
    return error


def error_response(
    *,
    description: str,
    code: str,
    message: str,
    details: Any | None = None,
) -> dict[str, Any]:
    """Build a reusable OpenAPI error response entry."""
    return {
        "model": ErrorResponse,
        "description": description,
        "content": {
            "application/json": {
                "example": _build_error_example(code=code, message=message, details=details),
            }
        },
    }


AUTHENTICATION_ERROR_RESPONSE = {
    status.HTTP_401_UNAUTHORIZED: error_response(
        description="Authentication failed or a bearer token was missing, invalid, expired, or tied to an inactive account.",
        code="authentication_error",
        message="Authentication is required to access this resource.",
    )
}

AUTHORIZATION_ERROR_RESPONSE = {
    status.HTTP_403_FORBIDDEN: error_response(
        description="The authenticated user is valid but does not have sufficient permissions for the requested action.",
        code="authorization_error",
        message="Administrator role is required.",
    )
}

NOT_FOUND_ERROR_RESPONSE = {
    status.HTTP_404_NOT_FOUND: error_response(
        description="The requested resource was not found.",
        code="not_found",
        message="Requested resource was not found.",
    )
}

CONFLICT_ERROR_RESPONSE = {
    status.HTTP_409_CONFLICT: error_response(
        description="The requested operation conflicts with the current stored state.",
        code="conflict",
        message="Resource conflict detected.",
    )
}

BUSINESS_VALIDATION_ERROR_RESPONSE = {
    status.HTTP_422_UNPROCESSABLE_CONTENT: error_response(
        description="The request reached application logic but violated a business validation rule.",
        code="validation_error",
        message="Validation failed.",
    )
}

VALIDATION_ERROR_RESPONSE = {
    status.HTTP_422_UNPROCESSABLE_CONTENT: error_response(
        description="The request failed request-schema validation or application-level validation rules.",
        code="validation_error",
        message="Validation failed.",
        details=[
            {
                "type": "validation_error",
                "loc": ["query", "sort_by"],
                "msg": "Unsupported sort field.",
                "input": "unsupported",
            }
        ],
    )
}

REQUEST_VALIDATION_ERROR_RESPONSE = {
    status.HTTP_422_UNPROCESSABLE_CONTENT: error_response(
        description="The request payload, path parameters, or query parameters failed schema validation.",
        code="request_validation_error",
        message="Request validation failed.",
        details=[
            {
                "type": "string_too_short",
                "loc": ["body", "password"],
                "msg": "String should have at least 8 characters",
                "input": "short",
            }
        ],
    )
}

INTERNAL_SERVER_ERROR_RESPONSE = {
    status.HTTP_500_INTERNAL_SERVER_ERROR: error_response(
        description="An unexpected server-side error occurred.",
        code="internal_server_error",
        message="An unexpected server error occurred.",
    )
}


def merge_openapi_responses(*response_sets: dict[int, dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Merge response dictionaries for route decorators."""
    merged: dict[int, dict[str, Any]] = {}
    for response_set in response_sets:
        merged.update(response_set)
    return merged
