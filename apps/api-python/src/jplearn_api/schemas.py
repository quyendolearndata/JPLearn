from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

EmailType = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"),
    Field(json_schema_extra={"format": "email"}),
]


class RegisterBody(BaseModel):
    email: EmailType
    password: str = Field(json_schema_extra={"minLength": 10})

    @field_validator("password")
    @classmethod
    def validate_password_length(cls, v: str) -> str:
        if len(v) < 10:
            raise ValueError("Password must be at least 10 characters")
        return v


class LoginBody(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)


class UserPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(json_schema_extra={"format": "uuid"})
    email: str
    roles: list[Literal["learner", "teacher", "admin"]]


class AuthSession(BaseModel):
    model_config = ConfigDict(extra="forbid")
    access_token: str
    user: UserPublic


class Flags(BaseModel):
    model_config = ConfigDict(extra="forbid")
    speaking_enabled: bool
    l1_subtitles_enabled: bool
    grammar_enabled: bool
    flashcards_enabled: bool


class CatalogItemWrite(BaseModel):
    topic_id: str = Field(min_length=1)
    ci_level: int
    duration_seconds: int = Field(gt=0)
    media_type: Literal["video", "audio"]
    visual_support: Literal["high", "medium", "low"]
    title_internal: str = Field(min_length=1)


class CatalogItemPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(json_schema_extra={"format": "uuid"})
    ci_level: int
    duration_seconds: int
    media_type: Literal["video", "audio"]
    topic_id: str
    visual_support: Literal["high", "medium", "low"]
    playback_url: str | None = Field(default=None, json_schema_extra={"format": "uri"})
    hls_url: str | None = Field(default=None, json_schema_extra={"format": "uri"})


class CatalogList(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[CatalogItemPublic]


class MediaAssetStaff(BaseModel):
    id: str = Field(json_schema_extra={"format": "uuid"})
    catalog_item_id: str
    storage_key: str
    playback_url: str
    hls_url: str | None = None
    mime: str


class CatalogItemStaff(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(json_schema_extra={"format": "uuid"})
    topic_id: str
    ci_level: int
    duration_seconds: int
    media_type: Literal["video", "audio"]
    visual_support: Literal["high", "medium", "low"]
    title_internal: str
    has_l1_translation: Literal[False]
    status: Literal["draft", "level_qa", "published", "archived"]



class SessionStartBody(BaseModel):
    device_class: Literal["web", "phone", "ipad"]


class LearningSessionPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(json_schema_extra={"format": "uuid"})
    device_class: Literal["web", "phone", "ipad"]
    started_at: str = Field(json_schema_extra={"format": "date-time"})
    ended_at: str | None = Field(default=None, json_schema_extra={"format": "date-time"})
    duration_seconds: int | None = None


class LearnerProgressPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    minutes_comprehensible: int = Field(ge=0)
    current_ci_level: int = Field(ge=0, le=4)

