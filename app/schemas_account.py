"""
Pydantic schemas for account management — /api/account.

default_modes and language are surfaced as their own AccountUpdate fields
(not a raw preferences dict) even though both are stored inside
User.preferences — these are the only preferences the frontend needs to
write today, and validating named fields is safer than accepting an
arbitrary preferences blob from the client. Future preferences get their
own named field the same way.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# Keep in sync with frontend/lib/i18n.ts's SUPPORTED_LANGUAGES.
SupportedLanguage = Literal["en", "es", "fr", "zh-Hans"]


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
    language: SupportedLanguage | None = None
