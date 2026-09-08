"""Handlers for content reports and staff moderation."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from uuid import uuid4

from jplearn_api.application.commands import (
    CreateContentReportCommand,
    PatchStaffContentReportCommand,
)
from jplearn_api.application.ports.unit_of_work import AsyncUnitOfWork
from jplearn_api.application.queries import (
    GetMyContentReportQuery,
    GetStaffContentReportQuery,
    ListMyContentReportsQuery,
    ListStaffContentReportsQuery,
)
from jplearn_api.domain.content_report import (
    ContentReport,
    ContentReportAudit,
    ReportCategory,
    ReportStatus,
)
from jplearn_api.domain.errors import (
    ConflictError,
    EntityNotFoundError,
    InvalidDomainStateError,
    QuotaExceededError,
)


async def handle_create_report(
    cmd: CreateContentReportCommand,
    uow: AsyncUnitOfWork,
) -> ContentReport:
    desc_clean = cmd.description.strip()
    if not (1 <= len(desc_clean) <= 1000):
        raise InvalidDomainStateError("Description must be between 1 and 1000 characters")

    try:
        category_enum = ReportCategory(cmd.category)
    except ValueError:
        raise InvalidDomainStateError(f"Invalid report category '{cmd.category}'")

    request_hash = None
    if cmd.idempotency_key:
        raw_hash = f"{cmd.catalog_item_id}:{cmd.content_version_id}:{cmd.scene_id or ''}:{cmd.position_ms}:{cmd.category}:{desc_clean}"
        request_hash = hashlib.sha256(raw_hash.encode()).hexdigest()
        existing = await uow.content_reports.find_by_idempotency_key(cmd.user_id, cmd.idempotency_key)
        if existing is not None:
            existing_report, saved_hash = existing
            if saved_hash != request_hash:
                raise ConflictError("Idempotency key reused with different request payload")
            return existing_report

    # 1. Check catalog item exists and is published
    catalog_item = await uow.catalog.get_by_id(cmd.catalog_item_id)
    if not catalog_item:
        raise EntityNotFoundError(f"Catalog item '{cmd.catalog_item_id}' not found")
    if catalog_item.status != "published":
        raise InvalidDomainStateError("Reports can only be submitted for published catalog items")

    # 2. Check content version exists, belongs to catalog item, and is published
    version = await uow.content.get_by_id(cmd.content_version_id)
    if not version or version.catalog_item_id != cmd.catalog_item_id:
        raise InvalidDomainStateError("Content version not found or does not belong to catalog item")
    if not version.is_published:
        raise InvalidDomainStateError("Reports can only be filed on currently published version")

    # 3. Check position_ms within catalog duration
    duration_ms = catalog_item.duration_seconds * 1000
    if cmd.position_ms < 0 or cmd.position_ms > duration_ms:
        raise InvalidDomainStateError(
            f"Position {cmd.position_ms}ms is out of bounds for catalog duration {duration_ms}ms"
        )

    # 4. Check scene_id if provided
    if cmd.scene_id:
        scene_found = any(s.id == cmd.scene_id for s in version.scenes)
        if not scene_found:
            raise InvalidDomainStateError("Scene does not belong to specified content version")

    # 5. Check daily quota (max 10 reports per user per UTC day)
    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = await uow.content_reports.count_today_by_user(cmd.user_id, start_of_day)
    if today_count >= 10:
        raise QuotaExceededError("Daily report limit of 10 reached")

    # 6. Create report
    report = ContentReport(
        id=f"rpt_{uuid4().hex[:16]}",
        user_id=cmd.user_id,
        catalog_item_id=cmd.catalog_item_id,
        content_version_id=cmd.content_version_id,
        scene_id=cmd.scene_id,
        position_ms=cmd.position_ms,
        category=category_enum,
        description=desc_clean,
        status=ReportStatus.OPEN,
        public_reply=None,
        internal_note=None,
        assignee_id=None,
        resolution_version_id=None,
        idempotency_key=cmd.idempotency_key,
        revision=1,
        created_at=now,
        updated_at=now,
    )
    created = await uow.content_reports.create(report, request_hash=request_hash)
    return created


async def handle_list_my_reports(
    query: ListMyContentReportsQuery,
    uow: AsyncUnitOfWork,
) -> tuple[list[ContentReport], int]:
    return await uow.content_reports.list_by_user(
        user_id=query.user_id,
        limit=query.limit,
        offset=query.offset,
    )


async def handle_get_my_report(
    query: GetMyContentReportQuery,
    uow: AsyncUnitOfWork,
) -> ContentReport:
    report = await uow.content_reports.get_by_id_for_user(query.user_id, query.report_id)
    if not report:
        raise EntityNotFoundError(f"Content report '{query.report_id}' not found")
    return report


async def handle_list_staff_reports(
    query: ListStaffContentReportsQuery,
    uow: AsyncUnitOfWork,
) -> tuple[list[ContentReport], int]:
    return await uow.content_reports.list_staff(
        status=query.status,
        category=query.category,
        catalog_item_id=query.catalog_item_id,
        limit=query.limit,
        offset=query.offset,
    )


async def handle_get_staff_report(
    query: GetStaffContentReportQuery,
    uow: AsyncUnitOfWork,
) -> tuple[ContentReport, list[ContentReportAudit]]:
    report = await uow.content_reports.get_by_id(query.report_id)
    if not report:
        raise EntityNotFoundError(f"Content report '{query.report_id}' not found")
    audits = await uow.content_reports.get_audit_logs(query.report_id)
    return report, audits


async def handle_patch_staff_report(
    cmd: PatchStaffContentReportCommand,
    uow: AsyncUnitOfWork,
) -> ContentReport:
    if cmd.status is not None:
        try:
            ReportStatus(cmd.status)
        except ValueError:
            raise InvalidDomainStateError(f"Invalid report status '{cmd.status}'")

    if cmd.resolution_version_id is not None and cmd.resolution_version_id != "":
        res_ver = await uow.content.get_by_id(cmd.resolution_version_id)
        if not res_ver:
            raise EntityNotFoundError(f"Resolution version '{cmd.resolution_version_id}' not found")
        if not res_ver.is_published:
            raise InvalidDomainStateError("Resolution version must be published and QA-approved")

    updated = await uow.content_reports.update_moderation(
        report_id=cmd.report_id,
        expected_revision=cmd.expected_revision,
        status=cmd.status,
        assignee_id=cmd.assignee_id,
        public_reply=cmd.public_reply,
        internal_note=cmd.internal_note,
        resolution_version_id=cmd.resolution_version_id,
        audit_actor_id=cmd.actor_id,
        audit_reason=cmd.reason,
    )
    return updated
