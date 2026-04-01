"""Unit tests for MongoDB transaction retry handling."""

from __future__ import annotations

import logging

import pytest
from pymongo.errors import OperationFailure

from app.db.transactions import (
    TRANSIENT_TRANSACTION_ERROR_LABEL,
    UNKNOWN_TRANSACTION_COMMIT_RESULT_LABEL,
    run_transaction_with_retry,
)


class FakeSession:
    """Minimal async session double used to exercise transaction retries."""

    def __init__(self, *, commit_outcomes: list[OperationFailure | None] | None = None) -> None:
        self.commit_outcomes = list(commit_outcomes or [])
        self.in_transaction = False
        self.abort_calls = 0
        self.commit_calls = 0

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        _ = (exc_type, exc, tb)
        return False

    def start_transaction(self, *args, **kwargs) -> None:
        _ = (args, kwargs)
        self.in_transaction = True

    async def commit_transaction(self) -> None:
        self.commit_calls += 1
        if self.commit_outcomes:
            outcome = self.commit_outcomes.pop(0)
            if outcome is not None:
                raise outcome
        self.in_transaction = False

    async def abort_transaction(self) -> None:
        self.abort_calls += 1
        self.in_transaction = False


def _build_labeled_operation_failure(message: str, label: str) -> OperationFailure:
    exc = OperationFailure(message)
    exc._add_error_label(label)
    return exc


def _build_start_session_stub(sessions: list[FakeSession]):
    async def _start_session() -> FakeSession:
        return sessions.pop(0)

    return _start_session


@pytest.mark.asyncio
async def test_run_transaction_with_retry_retries_transient_transaction_errors(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    first_session = FakeSession()
    second_session = FakeSession()
    sessions = [first_session, second_session]
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(
        "app.db.transactions.mongodb_manager.start_session",
        _build_start_session_stub(sessions),
    )
    monkeypatch.setattr("app.db.transactions.asyncio.sleep", fake_sleep)

    attempts = 0

    async def flaky_transaction(_: FakeSession) -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise _build_labeled_operation_failure(
                "Simulated transient transaction failure.",
                TRANSIENT_TRANSACTION_ERROR_LABEL,
            )
        return "committed"

    caplog.set_level(logging.WARNING)

    result = await run_transaction_with_retry(
        flaky_transaction,
        operation_name="unit_test_purchase",
        max_attempts=2,
        base_backoff_seconds=0.01,
    )

    assert result == "committed"
    assert attempts == 2
    assert sleep_calls == [0.01]
    assert first_session.abort_calls == 1
    assert second_session.commit_calls == 1
    assert "TransientTransactionError" in caplog.text


@pytest.mark.asyncio
async def test_run_transaction_with_retry_retries_unknown_commit_result_without_rerunning_callback(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    session = FakeSession(
        commit_outcomes=[
            _build_labeled_operation_failure(
                "Unknown commit result.",
                UNKNOWN_TRANSACTION_COMMIT_RESULT_LABEL,
            ),
            None,
        ]
    )
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(
        "app.db.transactions.mongodb_manager.start_session",
        _build_start_session_stub([session]),
    )
    monkeypatch.setattr("app.db.transactions.asyncio.sleep", fake_sleep)

    callback_calls = 0

    async def transaction_body(_: FakeSession) -> str:
        nonlocal callback_calls
        callback_calls += 1
        return "committed"

    caplog.set_level(logging.WARNING)

    result = await run_transaction_with_retry(
        transaction_body,
        operation_name="unit_test_commit",
        max_attempts=2,
        max_commit_attempts=2,
        base_backoff_seconds=0.01,
    )

    assert result == "committed"
    assert callback_calls == 1
    assert session.commit_calls == 2
    assert session.abort_calls == 0
    assert sleep_calls == [0.01]
    assert "UnknownTransactionCommitResult" in caplog.text


@pytest.mark.asyncio
async def test_run_transaction_with_retry_propagates_non_retryable_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession()
    monkeypatch.setattr(
        "app.db.transactions.mongodb_manager.start_session",
        _build_start_session_stub([session]),
    )

    async def failing_transaction(_: FakeSession) -> None:
        raise OperationFailure("Non-retryable failure.")

    with pytest.raises(OperationFailure, match="Non-retryable failure."):
        await run_transaction_with_retry(
            failing_transaction,
            operation_name="unit_test_failure",
            max_attempts=3,
            base_backoff_seconds=0,
        )

    assert session.abort_calls == 1
    assert session.commit_calls == 0


@pytest.mark.asyncio
async def test_run_transaction_with_retry_raises_after_exhausting_transient_transaction_retries(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    first_session = FakeSession()
    second_session = FakeSession()
    sessions = [first_session, second_session]
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(
        "app.db.transactions.mongodb_manager.start_session",
        _build_start_session_stub(sessions),
    )
    monkeypatch.setattr("app.db.transactions.asyncio.sleep", fake_sleep)

    attempts = 0

    async def always_transient(_: FakeSession) -> None:
        nonlocal attempts
        attempts += 1
        raise _build_labeled_operation_failure(
            "Persistent transient transaction failure.",
            TRANSIENT_TRANSACTION_ERROR_LABEL,
        )

    caplog.set_level(logging.WARNING)

    with pytest.raises(OperationFailure, match="Persistent transient transaction failure."):
        await run_transaction_with_retry(
            always_transient,
            operation_name="unit_test_transient_exhaustion",
            max_attempts=2,
            base_backoff_seconds=0.01,
        )

    assert attempts == 2
    assert sleep_calls == [0.01]
    assert first_session.abort_calls == 1
    assert second_session.abort_calls == 1
    assert "exhausted 2 attempts" in caplog.text


@pytest.mark.asyncio
async def test_run_transaction_with_retry_raises_after_exhausting_unknown_commit_result_retries(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    session = FakeSession(
        commit_outcomes=[
            _build_labeled_operation_failure(
                "Unknown commit result.",
                UNKNOWN_TRANSACTION_COMMIT_RESULT_LABEL,
            ),
            _build_labeled_operation_failure(
                "Unknown commit result.",
                UNKNOWN_TRANSACTION_COMMIT_RESULT_LABEL,
            ),
        ]
    )
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(
        "app.db.transactions.mongodb_manager.start_session",
        _build_start_session_stub([session]),
    )
    monkeypatch.setattr("app.db.transactions.asyncio.sleep", fake_sleep)

    callback_calls = 0

    async def transaction_body(_: FakeSession) -> str:
        nonlocal callback_calls
        callback_calls += 1
        return "committed"

    caplog.set_level(logging.WARNING)

    with pytest.raises(OperationFailure, match="Unknown commit result."):
        await run_transaction_with_retry(
            transaction_body,
            operation_name="unit_test_commit_exhaustion",
            max_attempts=2,
            max_commit_attempts=2,
            base_backoff_seconds=0.01,
        )

    assert callback_calls == 1
    assert session.commit_calls == 2
    assert session.abort_calls == 0
    assert sleep_calls == [0.01]
    assert "exhausted 2 commit attempts" in caplog.text
