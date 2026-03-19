"""Helpers for working with MongoDB identifiers."""

from bson import ObjectId

from app.core.exceptions import ValidationException


def is_valid_object_id(value: str) -> bool:
    """Return whether the provided string is a valid MongoDB ObjectId."""
    return ObjectId.is_valid(value)


def to_object_id(value: str) -> ObjectId:
    """Convert a string into an ObjectId or raise a validation exception."""
    if not is_valid_object_id(value):
        raise ValidationException("Invalid MongoDB identifier format.")
    return ObjectId(value)
