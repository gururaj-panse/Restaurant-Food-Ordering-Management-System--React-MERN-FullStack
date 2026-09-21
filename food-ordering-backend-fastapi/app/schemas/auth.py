"""Request shapes for the Authentication Module — matches routes/auth.ts's
express-validator fields exactly (email, password >= 6 chars, name)."""

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
