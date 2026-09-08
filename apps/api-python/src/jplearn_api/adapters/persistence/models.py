"""SQLAlchemy 2.0 mapping-only. Do not autogenerate or create_all (ADR-003 D2)."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    roles: Mapped[list["UserRole"]] = relationship(back_populates="user")


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(
        Enum("learner", "teacher", "admin", name="Role", create_type=False),
        primary_key=True,
    )
    user: Mapped[User] = relationship(back_populates="roles")


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (UniqueConstraint("user_id", "device_class"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"))
    device_class: Mapped[str] = mapped_column(
        Enum("web", "phone", "ipad", name="DeviceClass", create_type=False),
    )
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    label_internal: Mapped[str] = mapped_column(Text)


class CatalogItem(Base):
    __tablename__ = "catalog_items"
    __table_args__ = (
        CheckConstraint(
            "(status <> 'published') OR (has_l1_translation = false)",
            name="catalog_items_published_without_l1_translation",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    topic_id: Mapped[str] = mapped_column(Text, ForeignKey("topics.id"))
    ci_level: Mapped[int] = mapped_column(Integer)
    duration_seconds: Mapped[int] = mapped_column(Integer)
    media_type: Mapped[str] = mapped_column(
        Enum("video", "audio", name="MediaType", create_type=False),
    )
    visual_support: Mapped[str] = mapped_column(
        Enum("high", "medium", "low", name="VisualSupport", create_type=False),
    )
    has_l1_translation: Mapped[bool] = mapped_column(Boolean, default=False)
    spoken_language: Mapped[str] = mapped_column(Text, default="ja")
    status: Mapped[str] = mapped_column(
        Enum("draft", "level_qa", "published", "archived", name="CatalogStatus", create_type=False),
        default="draft",
    )
    title_internal: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text, ForeignKey("users.id"))
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    qa_round: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    reviews: Mapped[list["CatalogReview"]] = relationship(order_by="CatalogReview.qa_round")
    media: Mapped[list["MediaAsset"]] = relationship(back_populates="catalog_item")
    content_versions: Mapped[list["ContentVersion"]] = relationship(
        back_populates="catalog_item",
        cascade="all, delete-orphan",
    )


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    catalog_item_id: Mapped[str] = mapped_column(Text, ForeignKey("catalog_items.id"))
    storage_key: Mapped[str] = mapped_column(Text)
    playback_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    hls_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime: Mapped[str] = mapped_column(Text)
    measured_duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    hls_bundle_sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    catalog_item: Mapped["CatalogItem"] = relationship(back_populates="media")


class LearningSession(Base):
    __tablename__ = "learning_sessions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"))
    device_class: Mapped[str] = mapped_column(
        Enum("web", "phone", "ipad", name="DeviceClass", create_type=False),
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)


class SessionIdempotencyKey(Base):
    __tablename__ = "session_idempotency_keys"

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[str] = mapped_column(Text, ForeignKey("learning_sessions.id", ondelete="CASCADE"))
    request_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )



class LearnerProgress(Base):
    __tablename__ = "learner_progress"

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), primary_key=True)
    minutes_comprehensible: Mapped[int] = mapped_column(Integer, default=0)
    current_ci_level: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[bool] = mapped_column(Boolean, default=False)


class LearningEvent(Base):
    __tablename__ = "learning_events"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"))
    session_id: Mapped[str | None] = mapped_column(Text, ForeignKey("learning_sessions.id"), nullable=True)
    type: Mapped[str] = mapped_column(
        Enum(
            "session_started",
            "session_ended",
            "minutes_comprehensible",
            "level_exposed",
            name="EventType",
            create_type=False,
        ),
    )
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))


class ContentVersion(Base):
    __tablename__ = "content_versions"
    __table_args__ = (
        UniqueConstraint("catalog_item_id", "version_number", name="content_versions_item_version_key"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    catalog_item_id: Mapped[str] = mapped_column(Text, ForeignKey("catalog_items.id"))
    version_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    is_frozen: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    media_asset_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_hls_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    measured_duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    hls_bundle_sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_source: Mapped[str] = mapped_column(Text, server_default="legacy_metadata")
    catalog_item: Mapped["CatalogItem"] = relationship(back_populates="content_versions")
    scenes: Mapped[list["Scene"]] = relationship(
        back_populates="content_version",
        cascade="all, delete-orphan",
        order_by="Scene.scene_index",
    )


class Scene(Base):
    __tablename__ = "scenes"
    __table_args__ = (
        UniqueConstraint("content_version_id", "scene_index", name="scenes_version_index_key"),
        CheckConstraint(
            "start_time_seconds >= 0 AND end_time_seconds > start_time_seconds",
            name="scenes_timing_check",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    content_version_id: Mapped[str] = mapped_column(Text, ForeignKey("content_versions.id"))
    scene_index: Mapped[int] = mapped_column(Integer)
    start_time_seconds: Mapped[int] = mapped_column(Integer)
    end_time_seconds: Mapped[int] = mapped_column(Integer)
    title_jp: Mapped[str] = mapped_column(Text)
    transcript_jp: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    content_version: Mapped["ContentVersion"] = relationship(back_populates="scenes")


class Series(Base):
    __tablename__ = "series"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    ci_level: Mapped[str] = mapped_column(Text)
    topic_id: Mapped[str] = mapped_column(Text, ForeignKey("topics.id"))
    status: Mapped[str] = mapped_column(Text, default="draft", server_default="'draft'::text")
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )

    items: Mapped[list["SeriesItem"]] = relationship(
        back_populates="series",
        cascade="all, delete-orphan",
        order_by="SeriesItem.position",
    )


class SeriesItem(Base):
    __tablename__ = "series_items"
    __table_args__ = (
        PrimaryKeyConstraint("series_id", "position", name="series_items_pkey"),
        UniqueConstraint("series_id", "catalog_item_id", name="series_items_unique_item_key"),
    )

    series_id: Mapped[str] = mapped_column(Text, ForeignKey("series.id"))
    catalog_item_id: Mapped[str] = mapped_column(Text, ForeignKey("catalog_items.id"))
    position: Mapped[int] = mapped_column(Integer)

    series: Mapped["Series"] = relationship(back_populates="items")


class SavedScene(Base):
    __tablename__ = "saved_scenes"
    __table_args__ = (
        UniqueConstraint("user_id", "scene_id", name="saved_scenes_user_scene_unique"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"))
    scene_id: Mapped[str] = mapped_column(Text, ForeignKey("scenes.id"))
    saved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )

    user: Mapped["User"] = relationship()
    scene: Mapped["Scene"] = relationship()


class LearnerLibraryState(Base):
    __tablename__ = "learner_library_state"

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    collection_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )


class PersonalCollection(Base):
    __tablename__ = "personal_collections"
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="personal_collections_id_user_unique"),
        UniqueConstraint("user_id", "idempotency_key", name="personal_collections_user_idempotency_unique"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )

    scenes: Mapped[list["CollectionScene"]] = relationship(
        back_populates="collection",
        cascade="all, delete-orphan",
        order_by="CollectionScene.position",
    )


class CollectionScene(Base):
    __tablename__ = "collection_scenes"
    __table_args__ = (
        PrimaryKeyConstraint("collection_id", "position", name="collection_scenes_pkey"),
        UniqueConstraint("collection_id", "scene_id", name="collection_scenes_unique_scene"),
        ForeignKeyConstraint(
            ["collection_id", "user_id"],
            ["personal_collections.id", "personal_collections.user_id"],
            name="collection_scenes_collection_user_fkey",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["user_id", "scene_id"],
            ["saved_scenes.user_id", "saved_scenes.scene_id"],
            name="collection_scenes_saved_scene_fkey",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    )

    collection_id: Mapped[str] = mapped_column(Text)
    user_id: Mapped[str] = mapped_column(Text)
    scene_id: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )

    collection: Mapped["PersonalCollection"] = relationship(back_populates="scenes")


class ContentReport(Base):
    __tablename__ = "content_reports"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="content_reports_user_idempotency_unique"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id", ondelete="CASCADE"))
    catalog_item_id: Mapped[str] = mapped_column(Text, ForeignKey("catalog_items.id", ondelete="CASCADE"))
    content_version_id: Mapped[str] = mapped_column(Text, ForeignKey("content_versions.id", ondelete="CASCADE"))
    scene_id: Mapped[str | None] = mapped_column(Text, ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True)
    position_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="open", server_default="open")
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    assignee_id: Mapped[str | None] = mapped_column(Text, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    public_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_version_id: Mapped[str | None] = mapped_column(Text, ForeignKey("content_versions.id", ondelete="SET NULL"), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )

    audit_logs: Mapped[list["ContentReportAudit"]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="ContentReportAudit.created_at",
    )


class ContentReportAudit(Base):
    __tablename__ = "content_report_audit"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    report_id: Mapped[str] = mapped_column(Text, ForeignKey("content_reports.id", ondelete="CASCADE"))
    actor_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id", ondelete="CASCADE"))
    from_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_status: Mapped[str] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )

    report: Mapped["ContentReport"] = relationship(back_populates="audit_logs")


class LearnerPlaybackState(Base):
    __tablename__ = "learner_playback_state"

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    active_playback_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_epoch: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    device_class: Mapped[str] = mapped_column(Text)
    client_instance_id: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )


class Playback(Base):
    __tablename__ = "playbacks"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id", ondelete="CASCADE"))
    catalog_item_id: Mapped[str] = mapped_column(Text, ForeignKey("catalog_items.id", ondelete="CASCADE"))
    content_version_id: Mapped[str] = mapped_column(Text, ForeignKey("content_versions.id", ondelete="CASCADE"))
    epoch: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    device_class: Mapped[str] = mapped_column(Text)
    client_instance_id: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="active", server_default="active")
    last_seq: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    total_active_ms: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_position_ms: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_server_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    last_client_cumulative_ms: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class PlaybackReceipt(Base):
    __tablename__ = "playback_receipts"
    __table_args__ = (
        PrimaryKeyConstraint("playback_id", "seq", name="playback_receipts_pkey"),
    )

    playback_id: Mapped[str] = mapped_column(Text, ForeignKey("playbacks.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer)
    request_hash: Mapped[str] = mapped_column(Text)
    accepted_delta_ms: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cumulative_active_ms: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    response_payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )


class PlaybackCheckpoint(Base):
    __tablename__ = "playback_checkpoints"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "catalog_item_id", name="playback_checkpoints_pkey"),
    )

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id", ondelete="CASCADE"))
    catalog_item_id: Mapped[str] = mapped_column(Text, ForeignKey("catalog_items.id", ondelete="CASCADE"))
    content_version_id: Mapped[str] = mapped_column(Text, ForeignKey("content_versions.id", ondelete="CASCADE"))
    position_ms: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )


class LearningPreferences(Base):
    __tablename__ = "learning_preferences"

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    daily_goal_minutes: Mapped[int] = mapped_column(Integer, default=15, server_default="15")
    timezone: Mapped[str] = mapped_column(Text, default="Asia/Ho_Chi_Minh", server_default="Asia/Ho_Chi_Minh")
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    effective_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    preferred_topic_ids: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )


class LearnerDailyActivity(Base):
    __tablename__ = "learner_daily_activity"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "date", "policy_revision", name="learner_daily_activity_pkey"),
    )

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id", ondelete="CASCADE"))
    date: Mapped[str] = mapped_column(Text)
    policy_revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    timezone: Mapped[str] = mapped_column(Text, default="Asia/Ho_Chi_Minh", server_default="Asia/Ho_Chi_Minh")
    active_ms: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    goal_minutes: Mapped[int] = mapped_column(Integer, default=15, server_default="15")
    goal_met: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )


class HistoryDeletion(Base):
    __tablename__ = "history_deletions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(Text, default="queued", server_default="queued")
    cutoff_time: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    records_deleted: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class TranscriptRevision(Base):
    __tablename__ = "transcript_revisions"
    __table_args__ = (
        UniqueConstraint("catalog_item_id", "content_version_id", "revision", name="transcript_revisions_item_version_rev_key"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    catalog_item_id: Mapped[str] = mapped_column(Text, ForeignKey("catalog_items.id", ondelete="CASCADE"))
    content_version_id: Mapped[str] = mapped_column(Text, ForeignKey("content_versions.id", ondelete="CASCADE"))
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    status: Mapped[str] = mapped_column(Text, default="draft", server_default="draft")
    segments: Mapped[list[dict]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    provenance: Mapped[str] = mapped_column(Text, default="manual_teacher", server_default="manual_teacher")
    created_by: Mapped[str] = mapped_column(Text, ForeignKey("users.id", ondelete="RESTRICT"))
    approved_by: Mapped[str | None] = mapped_column(Text, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    return_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )


class ApprovedSceneText(Base):
    __tablename__ = "approved_scene_texts"
    __table_args__ = (
        UniqueConstraint("content_version_id", "scene_id", "transcript_revision_id", name="approved_scene_texts_version_scene_rev_key"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    catalog_item_id: Mapped[str] = mapped_column(Text, ForeignKey("catalog_items.id", ondelete="CASCADE"))
    content_version_id: Mapped[str] = mapped_column(Text, ForeignKey("content_versions.id", ondelete="CASCADE"))
    scene_id: Mapped[str] = mapped_column(Text, ForeignKey("scenes.id", ondelete="CASCADE"))
    transcript_revision_id: Mapped[str] = mapped_column(Text, ForeignKey("transcript_revisions.id", ondelete="CASCADE"))
    text_ja: Mapped[str] = mapped_column(Text)
    scene_index: Mapped[int] = mapped_column(Integer)
    start_time_seconds: Mapped[int] = mapped_column(Integer)
    end_time_seconds: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )


class LanguageAnalysisJob(Base):
    __tablename__ = "language_analysis_jobs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    catalog_item_id: Mapped[str] = mapped_column(Text, ForeignKey("catalog_items.id", ondelete="CASCADE"))
    transcript_revision_id: Mapped[str] = mapped_column(Text, ForeignKey("transcript_revisions.id", ondelete="CASCADE"))
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, default="queued", server_default="queued")
    results: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(Text, ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class AiQuotaAccountModel(Base):
    __tablename__ = "ai_quota_accounts"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str | None] = mapped_column(Text, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(Text)
    max_audio_seconds: Mapped[int] = mapped_column(Integer, default=3600, server_default="3600")
    max_input_tokens: Mapped[int] = mapped_column(Integer, default=1000000, server_default="1000000")
    max_output_tokens: Mapped[int] = mapped_column(Integer, default=500000, server_default="500000")
    max_cost_micros: Mapped[int] = mapped_column(BigInteger, default=10000000, server_default="10000000")
    reserved_audio_seconds: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    reserved_input_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    reserved_output_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    reserved_cost_micros: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    used_audio_seconds: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    used_input_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    used_output_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    used_cost_micros: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    policy_version: Mapped[str] = mapped_column(Text, default="v1", server_default="v1")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )


class AiUsageLedgerModel(Base):
    __tablename__ = "ai_usage_ledger"
    __table_args__ = (
        UniqueConstraint("account_id", "idempotency_key", "kind", name="ai_usage_ledger_account_idem_kind_key"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    account_id: Mapped[str] = mapped_column(Text, ForeignKey("ai_quota_accounts.id", ondelete="CASCADE"))
    job_id: Mapped[str] = mapped_column(Text)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id", ondelete="RESTRICT"))
    idempotency_key: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="reserved", server_default="reserved")
    provider: Mapped[str] = mapped_column(Text)
    provider_request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    audio_seconds: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cost_micros: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    currency: Mapped[str] = mapped_column(Text, default="USD", server_default="USD")
    policy_version: Mapped[str] = mapped_column(Text, default="v1", server_default="v1")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class ContentJobModel(Base):
    __tablename__ = "content_jobs"
    __table_args__ = (
        UniqueConstraint("created_by", "idempotency_key", name="content_jobs_user_idem_uniq"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    catalog_item_id: Mapped[str] = mapped_column(Text, ForeignKey("catalog_items.id", ondelete="CASCADE"))
    content_version_id: Mapped[str] = mapped_column(Text, ForeignKey("content_versions.id", ondelete="CASCADE"))
    task: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(Text, default="ja", server_default="ja")
    status: Mapped[str] = mapped_column(Text, default="queued", server_default="queued")
    progress: Mapped[float] = mapped_column(Float, default=0.0, server_default="0.0")
    provenance: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    source_hash: Mapped[str] = mapped_column(Text)
    config_hash: Mapped[str] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text, ForeignKey("users.id", ondelete="CASCADE"))
    attempt: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    attempt_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    result_draft: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    applied_by: Mapped[str | None] = mapped_column(Text, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP"),
    )


class AiAttemptModel(Base):
    __tablename__ = "ai_job_attempts"
    __table_args__ = (
        UniqueConstraint("job_id", "attempt_number", name="ai_attempt_job_number_key"),
        CheckConstraint("attempt_number > 0", name="ai_attempt_number_check"),
        CheckConstraint("state IN ('running','outcome_unknown','settled','not_billed')", name="ai_attempt_state_check"),
    )
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    job_id: Mapped[str] = mapped_column(Text, ForeignKey("content_jobs.id", ondelete="RESTRICT"))
    attempt_number: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(Text, unique=True)
    state: Mapped[str] = mapped_column(Text)
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    provider_request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    usage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(Text, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    resolution_hash: Mapped[str | None] = mapped_column(Text, nullable=True)


class CatalogReview(Base):
    __tablename__ = "catalog_reviews"
    __table_args__ = (
        UniqueConstraint("catalog_item_id", "qa_round", name="catalog_reviews_item_round_key"),
        CheckConstraint("decision IN ('approve', 'reject')", name="catalog_reviews_decision_check"),
        CheckConstraint("decision <> 'reject' OR length(btrim(notes)) > 0", name="catalog_reviews_reject_notes_check"),
    )
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    catalog_item_id: Mapped[str] = mapped_column(Text, ForeignKey("catalog_items.id"))
    qa_round: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text)
    reviewed_by: Mapped[str] = mapped_column(Text, ForeignKey("users.id"))
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))
