"""Adapter for transforming MongoDB documents into schema-friendly dictionaries."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

SchemaType = TypeVar("SchemaType", bound=BaseModel)


class MongoDocumentAdapter:
    """Normalize MongoDB documents before validation with Pydantic schemas."""

    @staticmethod
    def normalize(document: dict[str, Any] | None) -> dict[str, Any] | None:
        """Convert MongoDB's `_id` field into a string `id` field."""
        if document is None:
            return None
        normalized = dict(document)
        document_id = normalized.pop("_id", None)
        if document_id is not None:
            normalized["id"] = str(document_id)
        return normalized

    @classmethod
    def normalize_many(cls, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize a list of MongoDB documents."""
        return [item for item in (cls.normalize(document) for document in documents) if item]

    @classmethod
    def to_schema(cls, document: dict[str, Any] | None, schema: type[SchemaType]) -> SchemaType | None:
        """Normalize a MongoDB document and validate it using the given schema."""
        normalized = cls.normalize(document)
        if normalized is None:
            return None
        return schema.model_validate(normalized)
