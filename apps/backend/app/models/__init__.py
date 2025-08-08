"""SQLModel database models for the application."""

# Import User models from the original models.py file
import sys
import uuid
from pathlib import Path

from pydantic import EmailStr
from sqlmodel import (
    Field,
    SQLModel,  # Required for Alembic
)

from .scheduling import *  # noqa

# Import the User models directly since they exist in the original template
# This maintains compatibility with the existing FastAPI template


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=40)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=40)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=40)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=40)
    new_password: str = Field(min_length=8, max_length=40)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    # RBAC fields - will be populated via role assignments
    role: str | None = Field(
        default=None, max_length=50
    )  # Primary role for quick access
    department: str | None = Field(default=None, max_length=100, index=True)


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=40)


__all__ = [
    "SQLModel",
    # Scheduling models
    "Job",
    "Task",
    "Machine",
    "Operator",
    "Operation",
    "Skill",
    "ProductionZone",
    # User management models
    "User",
    "UserCreate",
    "UserUpdate",
    "UserRegister",
    "UserUpdateMe",
    "UpdatePassword",
    "UserPublic",
    "UsersPublic",
    "Message",
    "Token",
    "TokenPayload",
    "NewPassword",
]
