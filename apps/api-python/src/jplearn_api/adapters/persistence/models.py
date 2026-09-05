"""SQLAlchemy 2.0 mapping-only. Do not autogenerate or create_all (ADR-003 D2)."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
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
    media: Mapped[list["MediaAsset"]] = relationship(back_populates="catalog_item")


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    catalog_item_id: Mapped[str] = mapped_column(Text, ForeignKey("catalog_items.id"))
    storage_key: Mapped[str] = mapped_column(Text)
    playback_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    hls_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime: Mapped[str] = mapped_column(Text)
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
