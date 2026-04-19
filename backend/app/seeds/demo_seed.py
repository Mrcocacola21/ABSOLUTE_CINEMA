"""Explicit demo-data seeding command for coursework and presentation setups."""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorClientSession, AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.collections import DatabaseCollections
from app.db.database import mongodb_manager
from app.db.indexes import ensure_indexes
from app.db.transactions import run_transaction_with_retry
from app.db.validators import ensure_collection_validators
from app.seeds.demo_dataset import (
    DEMO_SEED_VERSION,
    DemoSeedData,
    build_demo_seed_data,
    demo_credentials,
    demo_seed_object_ids,
)

DOMAIN_COLLECTION_ORDER = (
    DatabaseCollections.TICKETS,
    DatabaseCollections.ORDERS,
    DatabaseCollections.SESSIONS,
    DatabaseCollections.MOVIES,
    DatabaseCollections.USERS,
)
INSERT_COLLECTION_ORDER = (
    DatabaseCollections.USERS,
    DatabaseCollections.MOVIES,
    DatabaseCollections.SESSIONS,
    DatabaseCollections.ORDERS,
    DatabaseCollections.TICKETS,
)

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class DemoSeedSummary:
    """Small summary returned after a successful demo seed run."""

    database_name: str
    reset_applied: bool
    seed_version: str
    counts: dict[str, int]
    movie_status_counts: dict[str, int]
    session_status_counts: dict[str, int]


async def seed_demo_database(
    *,
    reset: bool = False,
    reference_now: datetime | None = None,
    database: AsyncIOMotorDatabase | None = None,
) -> DemoSeedSummary:
    """Seed the configured MongoDB database with deterministic demo content."""
    created_connection = False
    try:
        if database is None:
            await mongodb_manager.connect()
            database = mongodb_manager.get_database()
            created_connection = True

        await ensure_collection_validators(database)
        await ensure_indexes(database)

        dataset = build_demo_seed_data(reference_now=reference_now)
        await run_transaction_with_retry(
            lambda db_session: _apply_seed_dataset(
                database=database,
                dataset=dataset,
                reset=reset,
                db_session=db_session,
            ),
            operation_name="seed_demo_data",
        )
        return _build_seed_summary(database=database, dataset=dataset, reset=reset)
    finally:
        if created_connection:
            await mongodb_manager.disconnect()


async def _apply_seed_dataset(
    *,
    database: AsyncIOMotorDatabase,
    dataset: DemoSeedData,
    reset: bool,
    db_session: AsyncIOMotorClientSession,
) -> None:
    if reset:
        for collection_name in DOMAIN_COLLECTION_ORDER:
            await database[collection_name].delete_many({}, session=db_session)
    else:
        for collection_name, object_ids in demo_seed_object_ids().items():
            await database[collection_name].delete_many(
                {"_id": {"$in": object_ids}},
                session=db_session,
            )

    documents_by_collection = {
        DatabaseCollections.USERS: dataset.users,
        DatabaseCollections.MOVIES: dataset.movies,
        DatabaseCollections.SESSIONS: dataset.sessions,
        DatabaseCollections.ORDERS: dataset.orders,
        DatabaseCollections.TICKETS: dataset.tickets,
    }
    for collection_name in INSERT_COLLECTION_ORDER:
        documents = documents_by_collection[collection_name]
        if documents:
            await database[collection_name].insert_many(documents, session=db_session, ordered=True)


def _build_seed_summary(
    *,
    database: AsyncIOMotorDatabase,
    dataset: DemoSeedData,
    reset: bool,
) -> DemoSeedSummary:
    movie_status_counts = Counter(str(movie["status"]) for movie in dataset.movies)
    session_status_counts = Counter(str(session["status"]) for session in dataset.sessions)
    return DemoSeedSummary(
        database_name=database.name,
        reset_applied=reset,
        seed_version=DEMO_SEED_VERSION,
        counts=dataset.collection_counts,
        movie_status_counts=dict(movie_status_counts),
        session_status_counts=dict(session_status_counts),
    )


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seed the configured MongoDB database with deterministic Cinema Showcase demo data.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear all domain collections before inserting the demo dataset.",
    )
    return parser


def _log_summary(summary: DemoSeedSummary) -> None:
    logger.info(
        "Seeded '%s' with %s (reset=%s).",
        summary.database_name,
        summary.seed_version,
        str(summary.reset_applied).lower(),
    )
    logger.info(
        "Counts: users=%s, movies=%s, sessions=%s, orders=%s, tickets=%s",
        summary.counts["users"],
        summary.counts["movies"],
        summary.counts["sessions"],
        summary.counts["orders"],
        summary.counts["tickets"],
    )
    logger.info("Movie statuses: %s", summary.movie_status_counts)
    logger.info("Session statuses: %s", summary.session_status_counts)
    logger.info("Demo accounts seeded. The shared demo password is intentionally not logged.")
    for credential in demo_credentials():
        logger.info(
            "  - role=%s email=%s name=%s",
            credential["role"],
            credential["email"],
            credential["name"],
        )


async def _async_main(reset: bool) -> None:
    summary = await seed_demo_database(reset=reset)
    _log_summary(summary)


def main() -> None:
    """Run the seed command from the command line."""
    configure_logging(get_settings().log_level)
    args = _build_argument_parser().parse_args()
    asyncio.run(_async_main(reset=bool(args.reset)))


if __name__ == "__main__":
    main()
