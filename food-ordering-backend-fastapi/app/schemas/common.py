"""Shared schema building blocks."""

from typing import Annotated, Any

from bson import ObjectId
from pydantic import BeforeValidator


def _validate_object_id(value: Any) -> str:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, str) and ObjectId.is_valid(value):
        return value
    raise ValueError("Invalid ObjectId")


# Represents a Mongo ObjectId as a plain string at the API boundary —
# matches the current Node backend, where JSON responses already serialize
# ObjectId as a string.
PyObjectId = Annotated[str, BeforeValidator(_validate_object_id)]


def mongo_to_jsonable(value: Any) -> Any:
    """
    Recursively converts raw bson.ObjectId values (in dicts/lists) to plain
    strings. Needed for routes that return populated Motor documents
    directly rather than through a Pydantic schema (e.g. Order module's
    getMyOrders, whose response embeds full restaurant/user documents) —
    FastAPI's default encoder does not know how to serialize a raw
    ObjectId. Mirrors Mongoose's automatic ObjectId -> string JSON
    serialization. `datetime` values are left as-is; FastAPI's standard
    response encoder already converts those to ISO-8601 strings.
    """
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, dict):
        return {key: mongo_to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [mongo_to_jsonable(item) for item in value]
    return value
