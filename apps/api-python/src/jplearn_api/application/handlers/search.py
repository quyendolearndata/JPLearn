"""Application handler for Japanese scene search."""

from __future__ import annotations

from jplearn_api.application.ports.unit_of_work import AsyncUnitOfWork
from jplearn_api.application.queries import SearchScenesQuery
from jplearn_api.application.read_models import SearchResponseDTO, SearchResultItemDTO
from jplearn_api.domain.errors import ForbiddenError
from jplearn_api.domain.search import normalize_search_query


async def handle_search_scenes(
    query: SearchScenesQuery,
    uow: AsyncUnitOfWork,
    search_enabled: bool = False,
) -> SearchResponseDTO:
    """Handle searching approved scene texts for authenticated learners."""
    if not search_enabled:
        raise ForbiddenError("Scene search is currently disabled")

    # 1. Normalize query (NFKC and length validation)
    normalized_q = normalize_search_query(query.q)

    # 2. Learner CI Level restriction
    async with uow:
        progress = await uow.learning.get_progress(query.user_id)
        learner_ci_level = progress.current_ci_level if progress is not None else 0

        # Effective max CI: clamped to learner's current CI level
        if query.ci_level is not None:
            effective_max_ci = min(query.ci_level, learner_ci_level)
        else:
            effective_max_ci = learner_ci_level

        # 3. Perform search in repository
        results, next_cursor, total_estimated = await uow.transcripts.search_approved_scenes(
            q=normalized_q,
            effective_max_ci=effective_max_ci,
            cursor=query.cursor,
            limit=query.limit,
        )

    # 4. Map to response DTOs
    items = [
        SearchResultItemDTO(
            catalog_item_id=r.catalog_item_id,
            content_version_id=r.content_version_id,
            scene_id=r.scene_id,
            scene_index=r.scene_index,
            start_time_seconds=r.start_time_seconds,
            end_time_seconds=r.end_time_seconds,
            matched_text_ja=r.matched_text_ja,
            highlight_spans=r.highlight_spans,
            match_kind=r.match_kind,
            ci_level=r.ci_level,
            topic_id=r.topic_id,
            title_jp=r.title_jp,
        )
        for r in results
    ]
    return SearchResponseDTO(
        items=items,
        next_cursor=next_cursor,
        total_estimated=total_estimated,
    )
