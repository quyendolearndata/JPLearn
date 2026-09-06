from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

class RegisterBody(BaseModel):
    email: str = Field(json_schema_extra={"format": "email"})
    password: str = Field(json_schema_extra={"minLength": 10})

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip()
        if not v or "@" not in v:
            raise ValueError("Invalid email format")
        return v

    @field_validator("password")
    @classmethod
    def validate_password_length(cls, v: str) -> str:
        if len(v) < 10:
            raise ValueError("Password must be at least 10 characters")
        return v


class LoginBody(BaseModel):
    email: str
    password: str


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
    topic_id: str
    ci_level: int
    duration_seconds: int
    media_type: Literal["video", "audio"]
    visual_support: Literal["high", "medium", "low"]
    title_internal: str


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



def _patch_contract(schema: dict) -> None:
    # Missing fields mean "unchanged"; explicit null is rejected by validate_patch.
    for prop in schema["properties"].values():
        variants = prop.pop("anyOf", [])
        for variant in variants:
            if variant.get("type") != "null":
                prop.update(variant)
        prop.pop("default", None)


class CatalogItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=_patch_contract)
    topic_id: str | None = Field(default=None, min_length=1)
    ci_level: int | None = Field(default=None, ge=0, le=4)
    duration_seconds: int | None = Field(default=None, ge=1)
    media_type: Literal["video", "audio"] | None = None
    visual_support: Literal["high", "medium", "low"] | None = None
    title_internal: str | None = Field(default=None, min_length=1, max_length=500)

    @field_validator("topic_id", "title_internal", mode="before")
    @classmethod
    def trim_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_patch(self):
        if not self.model_fields_set or any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("Provide at least one non-null metadata field")
        return self


class CatalogReviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    notes: str = Field(default="", max_length=2000)

    @field_validator("notes", mode="before")
    @classmethod
    def trim_notes(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def reject_needs_notes(self):
        if self.decision == "reject" and not self.notes:
            raise ValueError("Rejection requires notes")
        return self


class CatalogReviewPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    qa_round: int
    decision: Literal["approve", "reject"]
    notes: str
    reviewed_by: str
    reviewed_at: str = Field(json_schema_extra={"format": "date-time"})


class CatalogItemDetail(CatalogItemStaff):
    qa_round: int
    media: list[MediaAssetStaff]
    reviews: list[CatalogReviewPublic]


class CatalogStaffList(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[CatalogItemStaff]
