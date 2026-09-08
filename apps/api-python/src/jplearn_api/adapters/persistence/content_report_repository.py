"""SQLAlchemy implementation of ContentReportRepository."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.adapters.persistence.models import (
    ContentReport as OrmContentReport,
)
from jplearn_api.adapters.persistence.models import (
    ContentReportAudit as OrmContentReportAudit,
)
from jplearn_api.domain.content_report import (
    ContentReport,
    ContentReportAudit,
    ReportCategory,
    ReportStatus,
)
from jplearn_api.domain.errors import EntityNotFoundError, RevisionConflictError


class SqlAlchemyContentReportRepository:
    """SQLAlchemy adapter for ContentReportRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_domain(self, orm: OrmContentReport) -> ContentReport:
        return ContentReport(
            id=orm.id,
            user_id=orm.user_id,
            catalog_item_id=orm.catalog_item_id,
            content_version_id=orm.content_version_id,
            scene_id=orm.scene_id,
            position_ms=orm.position_ms or 0,
            category=ReportCategory(orm.category),
            description=orm.description,
            status=ReportStatus(orm.status),
            public_reply=orm.public_reply,
            internal_note=orm.internal_note,
            assignee_id=orm.assignee_id,
            resolution_version_id=orm.resolution_version_id,
            idempotency_key=orm.idempotency_key,
            revision=orm.revision,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    def _audit_to_domain(self, orm: OrmContentReportAudit) -> ContentReportAudit:
        return ContentReportAudit(
            id=orm.id,
            report_id=orm.report_id,
            actor_id=orm.actor_id,
            from_status=ReportStatus(orm.from_status) if orm.from_status else ReportStatus.OPEN,
            to_status=ReportStatus(orm.to_status),
            revision=orm.revision,
            reason=orm.reason,
            created_at=orm.created_at,
        )

    async def get_by_id(self, report_id: str) -> ContentReport | None:
        stmt = select(OrmContentReport).where(OrmContentReport.id == report_id)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return self._to_domain(orm) if orm else None

    async def get_by_id_for_user(self, user_id: str, report_id: str) -> ContentReport | None:
        stmt = select(OrmContentReport).where(
            OrmContentReport.id == report_id,
            OrmContentReport.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return self._to_domain(orm) if orm else None

    async def find_by_idempotency_key(
        self, user_id: str, idempotency_key: str
    ) -> tuple[ContentReport, str | None] | None:
        stmt = select(OrmContentReport).where(
            OrmContentReport.user_id == user_id,
            OrmContentReport.idempotency_key == idempotency_key,
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if not orm:
            return None
        return self._to_domain(orm), orm.request_hash

    async def count_today_by_user(self, user_id: str, start_of_day: datetime) -> int:
        stmt = select(func.count(OrmContentReport.id)).where(
            OrmContentReport.user_id == user_id,
            OrmContentReport.created_at >= start_of_day,
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def create(
        self,
        report: ContentReport,
        request_hash: str | None = None,
    ) -> ContentReport:
        now = datetime.now(UTC).replace(tzinfo=None)
        orm = OrmContentReport(
            id=report.id,
            user_id=report.user_id,
            catalog_item_id=report.catalog_item_id,
            content_version_id=report.content_version_id,
            scene_id=report.scene_id,
            position_ms=report.position_ms,
            category=report.category.value if isinstance(report.category, ReportCategory) else report.category,
            description=report.description,
            status=report.status.value if isinstance(report.status, ReportStatus) else report.status,
            revision=report.revision,
            assignee_id=report.assignee_id,
            public_reply=report.public_reply,
            internal_note=report.internal_note,
            resolution_version_id=report.resolution_version_id,
            idempotency_key=report.idempotency_key,
            request_hash=request_hash,
            created_at=report.created_at or now,
            updated_at=report.updated_at or now,
        )
        self._session.add(orm)
        await self._session.flush()
        return self._to_domain(orm)

    async def list_by_user(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ContentReport], int]:
        count_stmt = select(func.count(OrmContentReport.id)).where(OrmContentReport.user_id == user_id)
        total_res = await self._session.execute(count_stmt)
        total = total_res.scalar() or 0

        stmt = (
            select(OrmContentReport)
            .where(OrmContentReport.user_id == user_id)
            .order_by(desc(OrmContentReport.created_at), desc(OrmContentReport.id))
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        reports = [self._to_domain(row) for row in result.scalars().all()]
        return reports, total

    async def list_staff(
        self,
        status: str | None = None,
        category: str | None = None,
        catalog_item_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ContentReport], int]:
        conditions = []
        if status:
            conditions.append(OrmContentReport.status == status)
        if category:
            conditions.append(OrmContentReport.category == category)
        if catalog_item_id:
            conditions.append(OrmContentReport.catalog_item_id == catalog_item_id)

        count_stmt = select(func.count(OrmContentReport.id))
        if conditions:
            count_stmt = count_stmt.where(*conditions)
        total_res = await self._session.execute(count_stmt)
        total = total_res.scalar() or 0

        stmt = select(OrmContentReport)
        if conditions:
            stmt = stmt.where(*conditions)
        stmt = stmt.order_by(desc(OrmContentReport.updated_at), desc(OrmContentReport.id)).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        reports = [self._to_domain(row) for row in result.scalars().all()]
        return reports, total

    async def get_audit_logs(self, report_id: str) -> list[ContentReportAudit]:
        stmt = (
            select(OrmContentReportAudit)
            .where(OrmContentReportAudit.report_id == report_id)
            .order_by(OrmContentReportAudit.created_at.asc(), OrmContentReportAudit.revision.asc())
        )
        result = await self._session.execute(stmt)
        return [self._audit_to_domain(row) for row in result.scalars().all()]

    async def update_moderation(
        self,
        report_id: str,
        expected_revision: int,
        status: str | None = None,
        assignee_id: str | None = None,
        public_reply: str | None = None,
        internal_note: str | None = None,
        resolution_version_id: str | None = None,
        audit_actor_id: str | None = None,
        audit_reason: str | None = None,
    ) -> ContentReport:
        stmt = select(OrmContentReport).where(OrmContentReport.id == report_id).with_for_update()
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if not orm:
            raise EntityNotFoundError(f"Content report '{report_id}' not found")

        if orm.revision != expected_revision:
            raise RevisionConflictError(
                f"Expected revision {expected_revision}, but current revision is {orm.revision}"
            )

        from_status = orm.status
        now = datetime.now(UTC).replace(tzinfo=None)

        if status is not None:
            orm.status = status
        if assignee_id is not None:
            orm.assignee_id = assignee_id if assignee_id != "" else None
        if public_reply is not None:
            orm.public_reply = public_reply
        if internal_note is not None:
            orm.internal_note = internal_note
        if resolution_version_id is not None:
            orm.resolution_version_id = resolution_version_id if resolution_version_id != "" else None

        orm.revision += 1
        orm.updated_at = now

        if audit_actor_id:
            audit_entry = OrmContentReportAudit(
                id=f"cra_{uuid4().hex[:16]}",
                report_id=report_id,
                actor_id=audit_actor_id,
                from_status=from_status,
                to_status=orm.status,
                revision=orm.revision,
                reason=audit_reason,
                created_at=now,
            )
            self._session.add(audit_entry)

        await self._session.flush()
        return self._to_domain(orm)
