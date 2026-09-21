"""
User schemas — field-for-field match to CURRENT_STATE.md §4 / TARGET_ERD.md
`USER`. No field added, renamed, or made required beyond the confirmed
Mongoose schema.
"""

from pydantic import BaseModel, ConfigDict, EmailStr

from app.schemas.common import PyObjectId


class UserBase(BaseModel):
    email: EmailStr
    name: str | None = None
    addressLine1: str | None = None
    city: str | None = None
    country: str | None = None
    image: str | None = None


class UserInDB(UserBase):
    """Full stored document shape — password included, never returned as-is."""

    model_config = ConfigDict(populate_by_name=True)

    id: PyObjectId | None = None
    password: str  # bcrypt hash


class UserPublic(UserBase):
    """API-facing shape — matches what the current backend returns today (no password)."""

    id: PyObjectId
