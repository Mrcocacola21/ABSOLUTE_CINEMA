"""API tests for provider-neutral payment initiation endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.services import get_payment_service
from app.core.constants import (
    PaymentAttemptStatuses,
    PaymentStatuses,
    PaymentWebhookProcessingStatuses,
    RefundStatuses,
    Roles,
    TicketStatuses,
)
from app.main import create_application
from app.schemas.payment import (
    AdminPaymentCustomerRead,
    AdminPaymentDetailsRead,
    AdminPaymentListItemRead,
    AdminPaymentOrderContextRead,
    AdminPaymentTicketImpactRead,
    CustomerRefundRead,
    PaymentAttemptRead,
    PaymentDetailsRead,
    PaymentInitiationRead,
    PaymentReportMovieAggregateRead,
    PaymentReportPeriodRead,
    PaymentReportRead,
    PaymentReportSessionAggregateRead,
    PaymentReportSummaryRead,
    PaymentSimulationRead,
    PaymentWebhookEventRead,
    PaymentWebhookProcessingRead,
    RefundRead,
)
from app.schemas.user import UserRead


def build_user(*, role: str = Roles.USER) -> UserRead:
    return UserRead(
        id="user-1",
        name="Payment API User",
        email="payment-api@example.com",
        role=role,
        is_active=True,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=None,
    )


class FakePaymentApiService:
    def __init__(self) -> None:
        self.initiation_calls: list[dict[str, object]] = []
        self.refund_calls: list[dict[str, object]] = []
        self.report_calls: list[dict[str, object]] = []

    async def initiate_order_payment(self, **kwargs: object) -> PaymentInitiationRead:
        self.initiation_calls.append(kwargs)
        return PaymentInitiationRead(
            payment_id="payment-1",
            order_id=str(kwargs["order_id"]),
            provider="fake",
            status=PaymentStatuses.PENDING,
            amount_minor=12345,
            currency="UAH",
            attempt_id="attempt-1",
            attempt_status=PaymentAttemptStatuses.SUCCEEDED,
            provider_payment_id="fake-pay-payment-1",
            provider_attempt_id="fake-attempt-payment-1",
            redirect_url="https://payments.example.test/fake/fake-pay-payment-1",
            client_payload={"mode": "fake_redirect"},
            expires_at=datetime.now(tz=timezone.utc) + timedelta(minutes=10),
            reused=False,
        )

    async def retry_order_payment(self, **kwargs: object) -> PaymentInitiationRead:
        self.initiation_calls.append({"retry": True, **kwargs})
        return PaymentInitiationRead(
            payment_id="payment-retry-1",
            order_id=str(kwargs["order_id"]),
            provider="fake",
            status=PaymentStatuses.PENDING,
            amount_minor=12345,
            currency="UAH",
            attempt_id="attempt-retry-1",
            attempt_status=PaymentAttemptStatuses.SUCCEEDED,
            provider_payment_id="fake-pay-payment-retry-1",
            provider_attempt_id="fake-attempt-payment-retry-1",
            redirect_url="https://payments.example.test/fake/fake-pay-payment-retry-1",
            client_payload={"mode": "fake_redirect"},
            expires_at=datetime.now(tz=timezone.utc) + timedelta(minutes=10),
            reused=False,
        )

    async def get_payment_details(self, payment_id: str, *, current_user: UserRead) -> PaymentDetailsRead:
        _ = current_user
        return self._payment_details(payment_id=payment_id, order_id="order-1")

    async def get_order_payment_details(self, order_id: str, *, current_user: UserRead) -> PaymentDetailsRead:
        _ = current_user
        return self._payment_details(payment_id="payment-1", order_id=order_id)

    async def simulate_fake_provider_payment(
        self,
        payment_id: str,
        *,
        result: str,
        current_user: UserRead,
    ) -> PaymentSimulationRead:
        _ = current_user
        webhook = PaymentWebhookProcessingRead(
            event_id="webhook-simulated-1",
            provider="fake",
            provider_event_id=f"evt-demo-{result}",
            event_type="payment.updated",
            processing_status=PaymentWebhookProcessingStatuses.PROCESSED,
            duplicate=False,
            payment_id=payment_id,
            order_id="order-1",
            message="Payment webhook event processed.",
        )
        return PaymentSimulationRead(
            result=result,
            payment=self._payment_details(payment_id=payment_id, order_id="order-1"),
            webhook=webhook,
            message="Fake-provider simulation processed through the payment webhook pipeline.",
        )

    async def process_provider_webhook(
        self,
        *,
        raw_body: bytes,
        headers: dict[str, str] | None = None,
    ) -> PaymentWebhookProcessingRead:
        self.webhook_raw_body = raw_body
        self.webhook_headers = headers or {}
        return PaymentWebhookProcessingRead(
            event_id="webhook-1",
            provider="fake",
            provider_event_id="evt-paid-1",
            event_type="payment.updated",
            processing_status=PaymentWebhookProcessingStatuses.PROCESSED,
            duplicate=False,
            payment_id="payment-1",
            order_id="order-1",
            message="Payment webhook event processed.",
        )

    async def refund_payment(self, **kwargs: object) -> RefundRead:
        self.refund_calls.append(kwargs)
        return self._refund_read(
            refund_id="refund-1",
            payment_id=str(kwargs["payment_id"]),
            amount_minor=int(kwargs["amount_minor"] or 12345),
            reason=str(kwargs["reason"]),
            requested_by=str(kwargs["requested_by"]),
        )

    async def request_order_refund(
        self,
        *,
        order_id: str,
        payload: object,
        current_user: UserRead,
    ) -> CustomerRefundRead:
        self.refund_calls.append(
            {
                "order_id": order_id,
                "payload": payload,
                "current_user": current_user,
            }
        )
        refund = self._refund_read(
            refund_id="refund-1",
            payment_id="payment-1",
            amount_minor=2345,
            reason="customer_cancelled_ticket",
            requested_by=f"user:{current_user.id}",
        )
        payment = self._payment_details(payment_id="payment-1", order_id=order_id)
        return CustomerRefundRead(
            refund=refund,
            payment=payment,
            refunds=[refund],
            refunds_count=1,
            refunded_amount_minor=2345,
            remaining_refundable_amount_minor=10000,
            latest_refund_status=RefundStatuses.SUCCEEDED,
        )

    async def list_payment_refunds(self, payment_id: str, *, current_user: UserRead) -> list[RefundRead]:
        _ = current_user
        return [
            self._refund_read(
                refund_id="refund-1",
                payment_id=payment_id,
                amount_minor=2345,
                reason="customer_request",
                requested_by="admin-1",
            )
        ]

    async def list_order_refunds(self, order_id: str, *, current_user: UserRead) -> list[RefundRead]:
        _ = (order_id, current_user)
        return [
            self._refund_read(
                refund_id="refund-1",
                payment_id="payment-1",
                amount_minor=2345,
                reason="customer_request",
                requested_by="admin-1",
            )
        ]

    async def list_admin_payments(self, **kwargs: object) -> list[AdminPaymentListItemRead]:
        self.admin_list_kwargs = kwargs
        now = datetime.now(tz=timezone.utc)
        return [
            AdminPaymentListItemRead(
                id="payment-1",
                order_id="order-1",
                user_id="user-1",
                amount_minor=12345,
                currency="UAH",
                provider="fake",
                provider_payment_id="fake-pay-payment-1",
                idempotency_key="idem-payment-1",
                metadata=None,
                status=PaymentStatuses.SUCCEEDED,
                failure_code=None,
                failure_message=None,
                created_at=now,
                updated_at=now,
                attempts_count=2,
                refunds_count=1,
                refunded_amount_minor=2345,
                remaining_refundable_amount_minor=10000,
                refundable=True,
                latest_refund_status=RefundStatuses.SUCCEEDED,
                order_status="completed",
                customer_name="Payment API User",
                customer_email="payment-api@example.com",
            )
        ]

    async def get_admin_payment_details(self, payment_id: str) -> AdminPaymentDetailsRead:
        now = datetime.now(tz=timezone.utc)
        return AdminPaymentDetailsRead(
            id=payment_id,
            order_id="order-1",
            user_id="user-1",
            amount_minor=12345,
            currency="UAH",
            provider="fake",
            provider_payment_id="fake-pay-payment-1",
            idempotency_key="idem-payment-1",
            metadata=None,
            status=PaymentStatuses.SUCCEEDED,
            failure_code=None,
            failure_message=None,
            created_at=now,
            updated_at=now,
            attempts=[
                PaymentAttemptRead(
                    id="attempt-1",
                    payment_id=payment_id,
                    order_id="order-1",
                    provider="fake",
                    provider_attempt_id="fake-attempt-payment-1",
                    request_payload_snapshot={"operation": "create_payment"},
                    response_payload_snapshot={"status": PaymentStatuses.SUCCEEDED},
                    status=PaymentAttemptStatuses.SUCCEEDED,
                    error_code=None,
                    error_message=None,
                    created_at=now,
                    updated_at=now,
                )
            ],
            refunds=[
                self._refund_read(
                    refund_id="refund-1",
                    payment_id=payment_id,
                    amount_minor=2345,
                    reason="customer_request",
                    requested_by="admin-1",
                )
            ],
            webhook_events=[
                PaymentWebhookEventRead(
                    id="webhook-1",
                    provider="fake",
                    provider_event_id="evt-paid-1",
                    event_type="payment.updated",
                    signature_verified=True,
                    payload_hash="a" * 64,
                    payload_snapshot={"payment": {"id": "fake-pay-payment-1"}},
                    processing_status=PaymentWebhookProcessingStatuses.PROCESSED,
                    processed_at=now,
                    error_message=None,
                    payment_id=payment_id,
                    order_id="order-1",
                    refund_id=None,
                    created_at=now,
                    updated_at=now,
                )
            ],
            order=AdminPaymentOrderContextRead(
                order_id="order-1",
                order_status="completed",
                session_id="session-1",
                movie_id="movie-1",
                movie_title={"uk": "Тест", "en": "Test Movie"},
                session_start_time=now + timedelta(days=1),
                session_end_time=now + timedelta(days=1, hours=2),
                session_status="scheduled",
                total_price=123.45,
                tickets_count=2,
                seats=["1-1", "1-2"],
                tickets=[
                    AdminPaymentTicketImpactRead(
                        id="ticket-1",
                        seat_row=1,
                        seat_number=1,
                        seat_label="1-1",
                        price=61.72,
                        status=TicketStatuses.PURCHASED,
                    ),
                    AdminPaymentTicketImpactRead(
                        id="ticket-2",
                        seat_row=1,
                        seat_number=2,
                        seat_label="1-2",
                        price=61.73,
                        status=TicketStatuses.CANCELLED,
                        cancelled_at=now,
                        refund_id="refund-1",
                        refund_status=RefundStatuses.SUCCEEDED,
                        refund_amount_minor=2345,
                    ),
                ],
                expires_at=None,
            ),
            customer=AdminPaymentCustomerRead(
                user_id="user-1",
                name="Payment API User",
                email="payment-api@example.com",
            ),
            attempts_count=1,
            refunds_count=1,
            refunded_amount_minor=2345,
            remaining_refundable_amount_minor=10000,
            refundable=True,
            latest_refund_status=RefundStatuses.SUCCEEDED,
        )

    async def get_admin_payment_report(
        self,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> PaymentReportRead:
        self.report_calls.append({"date_from": date_from, "date_to": date_to})
        now = datetime.now(tz=timezone.utc)
        return PaymentReportRead(
            generated_at=now,
            period=PaymentReportPeriodRead(date_from=date_from, date_to=date_to),
            summary=PaymentReportSummaryRead(
                currency="UAH",
                total_payments_count=3,
                succeeded_payments_count=1,
                failed_payments_count=1,
                pending_payments_count=1,
                cancelled_payments_count=0,
                expired_payments_count=0,
                refunded_payments_count=0,
                partially_refunded_payments_count=1,
                gross_revenue_minor=12345,
                refunded_amount_minor=2345,
                net_revenue_minor=10000,
                succeeded_orders_count=1,
                paid_tickets_count=2,
                success_rate=1 / 3,
            ),
            sessions=[
                PaymentReportSessionAggregateRead(
                    session_id="session-1",
                    movie_id="movie-1",
                    movie_title={"uk": "Test Movie", "en": "Test Movie"},
                    session_start_time=now + timedelta(days=1),
                    session_end_time=now + timedelta(days=1, hours=2),
                    session_status="scheduled",
                    currency="UAH",
                    succeeded_payments_count=1,
                    succeeded_orders_count=1,
                    paid_tickets_count=2,
                    gross_revenue_minor=12345,
                    refunded_amount_minor=2345,
                    net_revenue_minor=10000,
                )
            ],
            movies=[
                PaymentReportMovieAggregateRead(
                    movie_id="movie-1",
                    movie_title={"uk": "Test Movie", "en": "Test Movie"},
                    currency="UAH",
                    paid_sessions_count=1,
                    succeeded_payments_count=1,
                    succeeded_orders_count=1,
                    paid_tickets_count=2,
                    gross_revenue_minor=12345,
                    refunded_amount_minor=2345,
                    net_revenue_minor=10000,
                )
            ],
        )

    def _payment_details(self, *, payment_id: str, order_id: str) -> PaymentDetailsRead:
        now = datetime.now(tz=timezone.utc)
        return PaymentDetailsRead(
            id=payment_id,
            order_id=order_id,
            user_id="user-1",
            amount_minor=12345,
            currency="UAH",
            provider="fake",
            provider_payment_id="fake-pay-payment-1",
            idempotency_key="idem-payment-1",
            metadata=None,
            status=PaymentStatuses.PENDING,
            failure_code=None,
            failure_message=None,
            created_at=now,
            updated_at=now,
            attempts=[
                PaymentAttemptRead(
                    id="attempt-1",
                    payment_id=payment_id,
                    order_id=order_id,
                    provider="fake",
                    provider_attempt_id="fake-attempt-payment-1",
                    request_payload_snapshot={"operation": "create_payment"},
                    response_payload_snapshot={"status": PaymentStatuses.PENDING},
                    status=PaymentAttemptStatuses.SUCCEEDED,
                    error_code=None,
                    error_message=None,
                    created_at=now,
                    updated_at=now,
                )
            ],
        )

    def _refund_read(
        self,
        *,
        refund_id: str,
        payment_id: str,
        amount_minor: int,
        reason: str,
        requested_by: str,
    ) -> RefundRead:
        now = datetime.now(tz=timezone.utc)
        return RefundRead(
            id=refund_id,
            payment_id=payment_id,
            order_id="order-1",
            user_id="user-1",
            amount_minor=amount_minor,
            currency="UAH",
            status=RefundStatuses.SUCCEEDED,
            provider="fake",
            provider_refund_id=f"fake-refund-{refund_id}",
            reason=reason,
            requested_by=requested_by,
            request_payload_snapshot={"operation": "refund_payment"},
            response_payload_snapshot={"status": RefundStatuses.SUCCEEDED},
            failure_code=None,
            failure_message=None,
            created_at=now,
            updated_at=now,
        )


@pytest.mark.asyncio
async def test_initiate_order_payment_endpoint_returns_provider_neutral_payload() -> None:
    app = create_application()
    service = FakePaymentApiService()
    app.dependency_overrides[get_current_user] = build_user
    app.dependency_overrides[get_payment_service] = lambda: service

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/orders/order-1/payments",
            headers={"Idempotency-Key": "idem-order-1"},
            json={
                "return_url": "http://localhost:5173/profile/orders/order-1",
                "metadata": {"source": "profile"},
            },
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Payment initiation prepared."
    assert body["data"]["payment_id"] == "payment-1"
    assert body["data"]["provider"] == "fake"
    assert body["data"]["redirect_url"].endswith("fake-pay-payment-1")
    assert service.initiation_calls[0]["idempotency_key"] == "idem-order-1"
    assert service.initiation_calls[0]["metadata"] == {"source": "profile"}


@pytest.mark.asyncio
async def test_payment_initiation_endpoint_rejects_conflicting_idempotency_keys() -> None:
    app = create_application()
    service = FakePaymentApiService()
    app.dependency_overrides[get_current_user] = build_user
    app.dependency_overrides[get_payment_service] = lambda: service

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/orders/order-1/payments",
            headers={"Idempotency-Key": "idem-header-1"},
            json={"idempotency_key": "idem-body-1"},
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"
    assert service.initiation_calls == []


@pytest.mark.asyncio
async def test_payment_inspection_endpoints_return_attempt_history() -> None:
    app = create_application()
    app.dependency_overrides[get_current_user] = build_user
    app.dependency_overrides[get_payment_service] = lambda: FakePaymentApiService()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        payment_response = await client.get("/api/v1/payments/payment-1")
        order_response = await client.get("/api/v1/orders/order-1/payment")

    assert payment_response.status_code == 200, payment_response.text
    assert order_response.status_code == 200, order_response.text
    assert payment_response.json()["data"]["attempts"][0]["id"] == "attempt-1"
    assert order_response.json()["data"]["order_id"] == "order-1"


@pytest.mark.asyncio
async def test_payment_simulation_endpoint_requires_auth_and_returns_webhook_result() -> None:
    app = create_application()
    app.dependency_overrides[get_current_user] = build_user
    app.dependency_overrides[get_payment_service] = lambda: FakePaymentApiService()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/v1/payments/payment-1/simulate", json={"result": "succeeded"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Fake payment simulation processed."
    assert body["data"]["result"] == "succeeded"
    assert body["data"]["webhook"]["processing_status"] == PaymentWebhookProcessingStatuses.PROCESSED
    assert body["data"]["payment"]["id"] == "payment-1"


@pytest.mark.asyncio
async def test_legacy_refund_create_is_rejected_and_refund_lists_remain_available() -> None:
    app = create_application()
    service = FakePaymentApiService()
    app.dependency_overrides[get_current_user] = lambda: build_user(role=Roles.ADMIN)
    app.dependency_overrides[get_payment_service] = lambda: service

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        create_response = await client.post(
            "/api/v1/payments/payment-1/refunds",
            json={"amount_minor": 2345, "reason": "customer_request", "metadata": {"source": "admin"}},
        )
        payment_list_response = await client.get("/api/v1/payments/payment-1/refunds")
        order_list_response = await client.get("/api/v1/orders/order-1/refunds")

    assert create_response.status_code == 403, create_response.text
    assert create_response.json()["error"]["message"] == (
        "Use the admin payment refund endpoint for administrator refund actions."
    )
    assert payment_list_response.status_code == 200, payment_list_response.text
    assert payment_list_response.json()["data"][0]["provider_refund_id"] == "fake-refund-refund-1"
    assert order_list_response.status_code == 200, order_list_response.text
    assert service.refund_calls == []


@pytest.mark.asyncio
async def test_customer_refund_request_endpoint_uses_authenticated_user_and_returns_refresh_data() -> None:
    app = create_application()
    service = FakePaymentApiService()
    app.dependency_overrides[get_current_user] = build_user
    app.dependency_overrides[get_payment_service] = lambda: service

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/orders/order-1/refunds/request",
            json={"scope": "tickets", "ticket_ids": ["ticket-1"]},
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["message"] == "Refund request created."
    assert body["data"]["refund"]["amount_minor"] == 2345
    assert body["data"]["payment"]["id"] == "payment-1"
    assert body["data"]["refunds_count"] == 1
    assert service.refund_calls[0]["order_id"] == "order-1"
    assert service.refund_calls[0]["payload"].scope == "tickets"
    assert service.refund_calls[0]["payload"].ticket_ids == ["ticket-1"]


@pytest.mark.asyncio
async def test_admin_cannot_use_customer_refund_request_endpoint() -> None:
    app = create_application()
    service = FakePaymentApiService()
    app.dependency_overrides[get_current_user] = lambda: build_user(role=Roles.ADMIN)
    app.dependency_overrides[get_payment_service] = lambda: service

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/orders/order-1/refunds/request",
            json={"scope": "tickets", "ticket_ids": ["ticket-1"]},
        )

    assert response.status_code == 403
    assert response.json()["error"]["message"] == (
        "Customer self-service routes are not available to administrator accounts."
    )
    assert service.refund_calls == []


@pytest.mark.asyncio
async def test_create_refund_endpoint_requires_admin_role() -> None:
    app = create_application()
    app.dependency_overrides[get_current_user] = build_user
    app.dependency_overrides[get_payment_service] = lambda: FakePaymentApiService()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/payments/payment-1/refunds",
            json={"amount_minor": 2345, "reason": "customer_request"},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "authorization_error"


@pytest.mark.asyncio
async def test_admin_payment_management_endpoints_return_lifecycle_history_and_refund() -> None:
    app = create_application()
    service = FakePaymentApiService()
    app.dependency_overrides[get_current_user] = lambda: build_user(role=Roles.ADMIN)
    app.dependency_overrides[get_payment_service] = lambda: service

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        list_response = await client.get(
            "/api/v1/admin/payments",
            params={"status": PaymentStatuses.SUCCEEDED, "search": "payment-api"},
        )
        details_response = await client.get("/api/v1/admin/payments/payment-1")
        refund_response = await client.post(
            "/api/v1/admin/payments/payment-1/refunds",
            json={"amount_minor": 1234, "reason": "admin_adjustment", "metadata": {"source": "payment_admin"}},
        )

    assert list_response.status_code == 200, list_response.text
    assert list_response.json()["data"][0]["refundable"] is True
    assert list_response.json()["data"][0]["attempts_count"] == 2
    assert service.admin_list_kwargs["status"] == PaymentStatuses.SUCCEEDED
    assert service.admin_list_kwargs["search"] == "payment-api"
    assert details_response.status_code == 200, details_response.text
    details = details_response.json()["data"]
    assert details["attempts"][0]["id"] == "attempt-1"
    assert details["refunds"][0]["id"] == "refund-1"
    assert details["webhook_events"][0]["payment_id"] == "payment-1"
    assert details["order"]["seats"] == ["1-1", "1-2"]
    assert details["order"]["tickets"][1]["seat_label"] == "1-2"
    assert details["order"]["tickets"][1]["refund_status"] == RefundStatuses.SUCCEEDED
    assert refund_response.status_code == 201, refund_response.text
    assert refund_response.json()["data"]["amount_minor"] == 1234
    assert service.refund_calls[-1]["requested_by"] == "admin:user-1"
    assert service.refund_calls[-1]["metadata"] == {"source": "payment_admin"}


@pytest.mark.asyncio
async def test_admin_payment_report_endpoint_returns_period_revenue_metrics() -> None:
    app = create_application()
    service = FakePaymentApiService()
    app.dependency_overrides[get_current_user] = lambda: build_user(role=Roles.ADMIN)
    app.dependency_overrides[get_payment_service] = lambda: service
    date_from = "2026-05-01T00:00:00+00:00"
    date_to = "2026-05-31T23:59:59+00:00"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/api/v1/admin/payments/report",
            params={"date_from": date_from, "date_to": date_to},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data"]["summary"]["gross_revenue_minor"] == 12345
    assert body["data"]["summary"]["refunded_amount_minor"] == 2345
    assert body["data"]["summary"]["net_revenue_minor"] == 10000
    assert body["data"]["sessions"][0]["session_id"] == "session-1"
    assert body["data"]["movies"][0]["movie_id"] == "movie-1"
    assert service.report_calls[0]["date_from"].isoformat() == date_from
    assert service.report_calls[0]["date_to"].isoformat() == date_to


@pytest.mark.asyncio
async def test_admin_payment_management_requires_admin_role() -> None:
    app = create_application()
    app.dependency_overrides[get_current_user] = build_user
    app.dependency_overrides[get_payment_service] = lambda: FakePaymentApiService()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/admin/payments")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "authorization_error"


@pytest.mark.asyncio
async def test_admin_payment_details_and_admin_refund_require_admin_role() -> None:
    app = create_application()
    app.dependency_overrides[get_current_user] = build_user
    app.dependency_overrides[get_payment_service] = lambda: FakePaymentApiService()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        details_response = await client.get("/api/v1/admin/payments/payment-1")
        refund_response = await client.post(
            "/api/v1/admin/payments/payment-1/refunds",
            json={"amount_minor": 1234, "reason": "admin_adjustment"},
        )

    assert details_response.status_code == 403
    assert details_response.json()["error"]["code"] == "authorization_error"
    assert refund_response.status_code == 403
    assert refund_response.json()["error"]["code"] == "authorization_error"


@pytest.mark.asyncio
async def test_admin_payment_report_requires_admin_role() -> None:
    app = create_application()
    app.dependency_overrides[get_current_user] = build_user
    app.dependency_overrides[get_payment_service] = lambda: FakePaymentApiService()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/admin/payments/report")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "authorization_error"


@pytest.mark.asyncio
async def test_retry_order_payment_endpoint_returns_provider_neutral_payload() -> None:
    app = create_application()
    service = FakePaymentApiService()
    app.dependency_overrides[get_current_user] = build_user
    app.dependency_overrides[get_payment_service] = lambda: service

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/orders/order-1/payments/retry",
            headers={"Idempotency-Key": "retry-order-1"},
            json={"metadata": {"source": "retry_button"}},
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Payment retry prepared."
    assert body["data"]["payment_id"] == "payment-retry-1"
    assert service.initiation_calls[0]["retry"] is True
    assert service.initiation_calls[0]["idempotency_key"] == "retry-order-1"


@pytest.mark.asyncio
async def test_payment_webhook_endpoint_reads_raw_body_and_returns_processing_result() -> None:
    app = create_application()
    service = FakePaymentApiService()
    app.dependency_overrides[get_payment_service] = lambda: service

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/payments/webhook",
            headers={"x-fake-payment-signature": "signed"},
            content=b'{"event_id":"evt-paid-1"}',
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["data"]["provider_event_id"] == "evt-paid-1"
    assert body["data"]["processing_status"] == PaymentWebhookProcessingStatuses.PROCESSED
    assert service.webhook_raw_body == b'{"event_id":"evt-paid-1"}'
    assert service.webhook_headers["x-fake-payment-signature"] == "signed"


@pytest.mark.asyncio
async def test_payment_initiation_endpoint_requires_authentication() -> None:
    app = create_application()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/v1/orders/order-1/payments", json={})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_error"
