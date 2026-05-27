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
        "payments",
        "tickets",
        "admin",
    ]


def test_openapi_uses_swagger_token_exchange_for_authorize_flow() -> None:
    app = create_application()
    spec = app.openapi()

    security_schemes = spec["components"]["securitySchemes"]
    scheme = security_schemes["OAuth2PasswordBearer"]
    refresh = spec["paths"]["/api/v1/auth/refresh"]["post"]

    assert scheme["type"] == "oauth2"
    assert scheme["flows"]["password"]["tokenUrl"] == "/api/v1/auth/token"
    assert "/api/v1/auth/token" not in spec["paths"]
    assert refresh["summary"] == "Refresh an expired access token"
    assert "refresh JWT" in refresh["description"]


def test_openapi_marks_protected_routes_and_error_contracts() -> None:
    app = create_application()
    spec = app.openapi()

    users_me = spec["paths"]["/api/v1/users/me"]["get"]
    admin_movies = spec["paths"]["/api/v1/admin/movies"]["get"]
    public_movies = spec["paths"]["/api/v1/movies"]["get"]
    schedule = spec["paths"]["/api/v1/schedule"]["get"]
    admin_session_create = spec["paths"]["/api/v1/admin/sessions"]["post"]
    admin_attendance = spec["paths"]["/api/v1/admin/attendance"]["get"]
    admin_tickets = spec["paths"]["/api/v1/admin/tickets"]["get"]
    admin_users = spec["paths"]["/api/v1/admin/users"]["get"]
    admin_payments = spec["paths"]["/api/v1/admin/payments"]["get"]
    admin_payment_report = spec["paths"]["/api/v1/admin/payments/report"]["get"]
    admin_payment_details = spec["paths"]["/api/v1/admin/payments/{payment_id}"]["get"]
    admin_payment_refund = spec["paths"]["/api/v1/admin/payments/{payment_id}/refunds"]["post"]

    assert users_me["security"] == [{"OAuth2PasswordBearer": []}]
    assert "401" in users_me["responses"]

    assert admin_movies["security"] == [{"OAuth2PasswordBearer": []}]
    assert "401" in admin_movies["responses"]
    assert "403" in admin_movies["responses"]
    assert admin_session_create["security"] == [{"OAuth2PasswordBearer": []}]
    assert "one-hall no-overlap" in admin_session_create["description"]
    assert admin_attendance["security"] == [{"OAuth2PasswordBearer": []}]
    assert "checked-in" in admin_attendance["description"]
    assert "newest purchase first" in admin_tickets["description"]
    assert "Password hashes" in admin_users["description"]
    assert admin_payments["security"] == [{"OAuth2PasswordBearer": []}]
    assert "remaining refundable amount" in admin_payments["description"]
    assert admin_payment_report["security"] == [{"OAuth2PasswordBearer": []}]
    assert "Gross revenue" in admin_payment_report["description"]
    assert "net revenue" in admin_payment_report["description"]
    assert "webhook history" in admin_payment_details["description"]
    assert "financial refund" in admin_payment_refund["description"]

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
    payment_initiation = spec["paths"]["/api/v1/orders/{order_id}/payments"]["post"]
    payment_retry = spec["paths"]["/api/v1/orders/{order_id}/payments/retry"]["post"]
    payment_details = spec["paths"]["/api/v1/payments/{payment_id}"]["get"]
    payment_simulation = spec["paths"]["/api/v1/payments/{payment_id}/simulate"]["post"]
    payment_refund_create = spec["paths"]["/api/v1/payments/{payment_id}/refunds"]["post"]
    payment_refunds = spec["paths"]["/api/v1/payments/{payment_id}/refunds"]["get"]
    customer_refund_request = spec["paths"]["/api/v1/orders/{order_id}/refunds/request"]["post"]
    order_refunds = spec["paths"]["/api/v1/orders/{order_id}/refunds"]["get"]
    payment_webhook = spec["paths"]["/api/v1/payments/webhook"]["post"]
    my_orders = spec["paths"]["/api/v1/users/me/orders"]["get"]

    assert register["summary"] == "Register a new user"
    assert "clients cannot self-register as administrators" in register["description"]
    assert login["summary"] == "Log in and receive access and refresh tokens"
    assert "form-encoded credentials" in login["description"]
    assert "data.refresh_token" in login["description"]

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
    assert payment_initiation["security"] == [{"OAuth2PasswordBearer": []}]
    assert "provider-neutral payment" in payment_initiation["description"]
    assert payment_retry["security"] == [{"OAuth2PasswordBearer": []}]
    assert "seat reservation is still active" in payment_retry["description"]
    assert payment_details["security"] == [{"OAuth2PasswordBearer": []}]
    assert payment_simulation["security"] == [{"OAuth2PasswordBearer": []}]
    assert "Development/demo-only" in payment_simulation["description"]
    assert "same webhook processor" in payment_simulation["description"]
    assert payment_refund_create["security"] == [{"OAuth2PasswordBearer": []}]
    assert "financial refund" in payment_refund_create["description"]
    assert customer_refund_request["security"] == [{"OAuth2PasswordBearer": []}]
    assert "partial refund" in customer_refund_request["description"]
    assert "remaining refundable payment amount" in customer_refund_request["description"]
    assert payment_refunds["security"] == [{"OAuth2PasswordBearer": []}]
    assert order_refunds["security"] == [{"OAuth2PasswordBearer": []}]
    assert "signature" in payment_webhook["description"]
    assert "security" not in payment_webhook
    assert my_orders["security"] == [{"OAuth2PasswordBearer": []}]

    ticket_schema = spec["components"]["schemas"]["TicketPurchaseRequest"]
    order_schema = spec["components"]["schemas"]["OrderPurchaseRequest"]
    payment_schema = spec["components"]["schemas"]["PaymentInitiationRequest"]
    payment_simulation_schema = spec["components"]["schemas"]["PaymentSimulationRequest"]
    payment_simulation_read_schema = spec["components"]["schemas"]["PaymentSimulationRead"]
    customer_refund_schema = spec["components"]["schemas"]["CustomerRefundRequest"]
    customer_refund_read_schema = spec["components"]["schemas"]["CustomerRefundRead"]
    webhook_schema = spec["components"]["schemas"]["PaymentWebhookProcessingRead"]
    refund_schema = spec["components"]["schemas"]["RefundRead"]
    assert ticket_schema["additionalProperties"] is False
    assert ticket_schema["properties"]["seat_row"]["description"].startswith("One-based seat row")
    assert order_schema["additionalProperties"] is False
    assert "Unique seat coordinates" in order_schema["properties"]["seats"]["description"]
    assert payment_schema["additionalProperties"] is False
    assert "return_url" in payment_schema["properties"]
    assert payment_simulation_schema["additionalProperties"] is False
    assert "result" in payment_simulation_schema["properties"]
    assert "webhook" in payment_simulation_read_schema["properties"]
    assert customer_refund_schema["additionalProperties"] is False
    assert customer_refund_schema["properties"]["scope"]["default"] == "order"
    assert "refund" in customer_refund_read_schema["properties"]
    assert "remaining_refundable_amount_minor" in customer_refund_read_schema["properties"]
    assert "duplicate" in webhook_schema["properties"]
    assert "refund_id" in webhook_schema["properties"]
    assert "requested_by" in refund_schema["properties"]
    assert "response_payload_snapshot" in refund_schema["properties"]


def test_openapi_documents_admin_movie_session_and_reporting_schemas() -> None:
    app = create_application()
    spec = app.openapi()

    schemas = spec["components"]["schemas"]
    for schema_name in [
        "MovieCreate",
        "MovieUpdate",
        "MovieRead",
        "SessionCreate",
        "SessionUpdate",
        "SessionDetailsRead",
        "TicketListRead",
        "UserRead",
        "AttendanceReportRead",
        "AttendanceSessionDetailsRead",
        "OrderValidationRead",
        "AdminPaymentListItemRead",
        "AdminPaymentDetailsRead",
        "PaymentReportRead",
        "PaymentReportSummaryRead",
        "PaymentReportSessionAggregateRead",
        "PaymentReportMovieAggregateRead",
        "PaymentWebhookEventRead",
        "RefundRead",
    ]:
        assert schema_name in schemas

    movie_create = schemas["MovieCreate"]
    movie_update = schemas["MovieUpdate"]
    session_create = schemas["SessionCreate"]
    attendance_report = schemas["AttendanceReportRead"]
    attendance_details = schemas["AttendanceSessionDetailsRead"]
    order_validation = schemas["OrderValidationRead"]
    admin_order_validation = spec["paths"]["/api/v1/admin/orders/validate/{token}"]["get"]

    assert movie_create["additionalProperties"] is False
    assert movie_create["properties"]["status"]["enum"] == ["planned", "active", "deactivated"]
    assert movie_update["properties"]["genres"]["description"].startswith("Updated list of normalized genre codes")
    assert session_create["additionalProperties"] is False
    assert session_create["properties"]["price"]["maximum"] == 1000.0
    assert "total_checked_in_tickets" in attendance_report["properties"]
    assert "total_cancelled_tickets" in attendance_report["properties"]
    assert "cancelled_tickets" in attendance_details["properties"]
    assert "unchecked_active_tickets_count" in attendance_details["properties"]
    assert "validity_code" in order_validation["properties"]
    assert "entry_status_code" not in order_validation["properties"]
    assert admin_order_validation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "ApiResponse_OrderValidationRead_"
    )
    assert "remaining_refundable_amount_minor" in schemas["AdminPaymentListItemRead"]["properties"]
    assert "webhook_events" in schemas["AdminPaymentDetailsRead"]["properties"]
    assert "summary" in schemas["PaymentReportRead"]["properties"]
    assert "gross_revenue_minor" in schemas["PaymentReportSummaryRead"]["properties"]
    assert "refunded_amount_minor" in schemas["PaymentReportSessionAggregateRead"]["properties"]
    assert "paid_sessions_count" in schemas["PaymentReportMovieAggregateRead"]["properties"]
    assert "payment_id" in schemas["PaymentWebhookEventRead"]["properties"]
    assert "refund_id" in schemas["PaymentWebhookEventRead"]["properties"]


def test_openapi_session_examples_use_future_demo_dates() -> None:
    app = create_application()
    spec = app.openapi()

    create_body = spec["paths"]["/api/v1/admin/sessions"]["post"]["requestBody"]
    update_body = spec["paths"]["/api/v1/admin/sessions/{session_id}"]["patch"]["requestBody"]

    create_example = create_body["content"]["application/json"]["examples"]["single_session"]["value"]
    batch_example = spec["paths"]["/api/v1/admin/sessions/batch"]["post"]["requestBody"]["content"][
        "application/json"
    ]["examples"]["batch_session"]["value"]
    update_example = update_body["content"]["application/json"]["examples"]["session_update"]["value"]

    assert create_example["start_time"].startswith("2026-05-06")
    assert batch_example["dates"] == ["2026-05-06", "2026-05-07", "2026-05-08"]
    assert update_example["start_time"].startswith("2026-05-06")
