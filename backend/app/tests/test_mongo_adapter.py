"""Unit tests for MongoDB document normalization."""

from __future__ import annotations

from bson import ObjectId
from pydantic import BaseModel

from app.adapters.mongo_adapter import MongoDocumentAdapter


class DemoSchema(BaseModel):
    id: str
    name: str


def test_normalize_returns_none_for_missing_document() -> None:
    assert MongoDocumentAdapter.normalize(None) is None


def test_normalize_converts_mongodb_id_to_string_id_without_mutating_input() -> None:
    object_id = ObjectId()
    document = {
        "_id": object_id,
        "name": "Cinema",
    }

    normalized = MongoDocumentAdapter.normalize(document)

    assert normalized == {
        "id": str(object_id),
        "name": "Cinema",
    }
    assert document == {
        "_id": object_id,
        "name": "Cinema",
    }


def test_normalize_preserves_documents_without_mongodb_id() -> None:
    document = {"id": "existing-id", "name": "Cinema"}

    assert MongoDocumentAdapter.normalize(document) == document


def test_normalize_many_normalizes_documents_and_drops_empty_results() -> None:
    object_id = ObjectId()

    assert MongoDocumentAdapter.normalize_many(
        [
            {"_id": object_id, "name": "Cinema"},
            {},
        ]
    ) == [
        {
            "id": str(object_id),
            "name": "Cinema",
        }
    ]


def test_to_schema_returns_none_for_missing_document() -> None:
    assert MongoDocumentAdapter.to_schema(None, DemoSchema) is None


def test_to_schema_validates_normalized_document() -> None:
    object_id = ObjectId()

    schema = MongoDocumentAdapter.to_schema(
        {
            "_id": object_id,
            "name": "Cinema",
        },
        DemoSchema,
    )

    assert schema == DemoSchema(id=str(object_id), name="Cinema")
