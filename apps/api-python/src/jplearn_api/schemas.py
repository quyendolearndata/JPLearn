from pydantic import BaseModel, ConfigDict


class RegisterBody(BaseModel):
    email: str
    password: str


class LoginBody(BaseModel):
    email: str
    password: str


class UserPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    email: str
    roles: list[str]


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
    media_type: str
    visual_support: str
    title_internal: str


class CatalogItemPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    ci_level: int
    duration_seconds: int
    media_type: str
    topic_id: str
    visual_support: str
    playback_url: str | None = None
    hls_url: str | None = None


class CatalogList(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[CatalogItemPublic]


class MediaAssetStaff(BaseModel):
    id: str
    catalog_item_id: str
    storage_key: str
    playback_url: str
    hls_url: str | None = None
    mime: str


class CatalogItemStaff(BaseModel):
    id: str
    topic_id: str
    ci_level: int
    duration_seconds: int
    media_type: str
    visual_support: str
    title_internal: str
    has_l1_translation: bool
    spoken_language: str
    status: str
    created_by: str
    media: list[MediaAssetStaff]


class SessionStartBody(BaseModel):
    device_class: str


class LearningSessionPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    device_class: str
    started_at: str
    ended_at: str | None = None
    duration_seconds: int | None = None


class LearnerProgressPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    minutes_comprehensible: int
    current_ci_level: int
