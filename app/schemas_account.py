"""
Pydantic schemas for account management — /api/account.

default_modes is surfaced as its own AccountUpdate field (not a raw
preferences dict) even though it's stored inside User.preferences — this is
the only preference the frontend needs to write today, and validating a
named field is safer than accepting an arbitrary preferences blob from the
client. Future preferences get their own named field the same way.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str | None
    avatar_url: str | None
    preferences: dict[str, Any]


class AccountUpdate(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=200)
    default_modes: list[str] | None = None
