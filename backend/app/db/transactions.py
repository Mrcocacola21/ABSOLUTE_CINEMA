"""Reusable MongoDB transaction runner with bounded retry handling."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from motor.motor_asyncio import AsyncIOMotorClientSession
from pymongo.errors import PyMongoError
from pymongo.read_concern import ReadConcern
from pymongo.read_preferences import ReadPreference
from pymongo.write_concern import WriteConcern

from app.core.logging import get_logger
from app.db.database import mongodb_manager

logger = get_logger(__name__)

T = TypeVar("T")
TransactionCallback = Callable[[AsyncIOMotorClientSession], Awaitable[T]]

DEFAULT_TRANSACTION_MAX_ATTEMPTS = 4
DEFAULT_TRANSACTION_BACKOFF_SECONDS = 0.05
DEFAULT_TRANSACTION_COMMIT_MAX_ATTEMPTS = 4

TRANSIENT_TRANSACTION_ERROR_LABEL = "TransientTransactionError"
UNKNOWN_TRANSACTION_COMMIT_RESULT_LABEL = "UnknownTransactionCommitResult"


def _has_error_label(exc: BaseException, label: str) -> bool:
    has_error_label = getattr(exc, "has_error_label", None)
    return bool(callable(has_error_label) and has_error_label(label))


def _transaction_retry_label(exc: BaseException) -> str | None:
    if _has_error_label(exc, TRANSIENT_TRANSACTION_ERROR_LABEL):
        return TRANSIENT_TRANSACTION_ERROR_LABEL
    return None


def _compute_backoff_seconds(*, base_backoff_seconds: float, attempt: int) -> float:
    return base_backoff_seconds * attempt


async def _abort_transaction_if_needed(
    db_session: AsyncIOMotorClientSession,
    *,
    operation_name: str,
    attempt: int,
) -> None:
    if not getattr(db_session, "in_transaction", False):
        return

    try:
        await db_session.abort_transaction()
    except PyMongoError as exc:  # pragma: no cover - defensive driver failure path
        logger.warning(
            "MongoDB transaction '%s' failed to abort cleanly on attempt %s.",
            operation_name,
            attempt,
            exc_info=exc,
        )


async def _commit_transaction_with_retry(
    db_session: AsyncIOMotorClientSession,
    *,
    operation_name: str,
    transaction_attempt: int,
    max_transaction_attempts: int,
    max_commit_attempts: int,
    base_backoff_seconds: float,
) -> None:
    commit_attempt = 1

    while True:
        try:
            await db_session.commit_transaction()
            return
        except PyMongoError as exc:
            if (
                _has_error_label(exc, UNKNOWN_TRANSACTION_COMMIT_RESULT_LABEL)
                and commit_attempt < max_commit_attempts
            ):
                delay = _compute_backoff_seconds(
                    base_backoff_seconds=base_backoff_seconds,
                    attempt=commit_attempt,
                )
                logger.warning(
                    "Retrying MongoDB transaction commit for '%s' after %s "
                    "(transaction attempt %s/%s, commit attempt %s/%s, backoff %.2fs).",
                    operation_name,
                    UNKNOWN_TRANSACTION_COMMIT_RESULT_LABEL,
                    transaction_attempt,
                    max_transaction_attempts,
                    commit_attempt + 1,
                    max_commit_attempts,
                    delay,
                )
                commit_attempt += 1
                await asyncio.sleep(delay)
                continue

            raise


async def run_transaction_with_retry(
    callback: TransactionCallback[T],
    *,
    operation_name: str,
    max_attempts: int = DEFAULT_TRANSACTION_MAX_ATTEMPTS,
    base_backoff_seconds: float = DEFAULT_TRANSACTION_BACKOFF_SECONDS,
    max_commit_attempts: int = DEFAULT_TRANSACTION_COMMIT_MAX_ATTEMPTS,
) -> T:
    """Run a MongoDB transaction with bounded retries for transient failures."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1.")
    if max_commit_attempts < 1:
        raise ValueError("max_commit_attempts must be at least 1.")
    if base_backoff_seconds < 0:
        raise ValueError("base_backoff_seconds cannot be negative.")

    for attempt in range(1, max_attempts + 1):
        logger.info(
            "Running MongoDB transaction '%s' attempt %s/%s.",
            operation_name,
            attempt,
            max_attempts,
        )
        async with await mongodb_manager.start_session() as db_session:
            db_session.start_transaction(
                read_concern=ReadConcern("snapshot"),
                write_concern=WriteConcern("majority"),
                read_preference=ReadPreference.PRIMARY,
            )

            try:
                result = await callback(db_session)
                await _commit_transaction_with_retry(
                    db_session,
                    operation_name=operation_name,
                    transaction_attempt=attempt,
                    max_transaction_attempts=max_attempts,
                    max_commit_attempts=max_commit_attempts,
                    base_backoff_seconds=base_backoff_seconds,
                )
                return result
            except Exception as exc:
                unknown_commit_result = _has_error_label(exc, UNKNOWN_TRANSACTION_COMMIT_RESULT_LABEL)
                if not unknown_commit_result:
                    await _abort_transaction_if_needed(
                        db_session,
                        operation_name=operation_name,
                        attempt=attempt,
                    )
                retry_label = _transaction_retry_label(exc)
                if retry_label is not None and attempt < max_attempts:
                    delay = _compute_backoff_seconds(
                        base_backoff_seconds=base_backoff_seconds,
                        attempt=attempt,
                    )
                    logger.warning(
                        "Retrying MongoDB transaction '%s' after %s on attempt %s/%s. Backing off %.2fs.",
                        operation_name,
                        retry_label,
                        attempt,
                        max_attempts,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                if retry_label is not None:
                    logger.error(
                        "MongoDB transaction '%s' exhausted %s attempts because of %s.",
                        operation_name,
                        max_attempts,
                        retry_label,
                    )
                if unknown_commit_result:
                    logger.error(
                        "MongoDB transaction '%s' exhausted %s commit attempts because of %s.",
                        operation_name,
                        max_commit_attempts,
                        UNKNOWN_TRANSACTION_COMMIT_RESULT_LABEL,
                    )
                raise

    raise RuntimeError("Transaction retry loop exited unexpectedly.")
