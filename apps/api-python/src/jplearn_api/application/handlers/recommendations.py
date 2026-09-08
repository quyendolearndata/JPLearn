"""Application handler for learner recommendations (UC-L16/UC-L17, Đợt C).

Enforces:
- Deterministic rule-based ranking (no ML, no dedicated table).
- Strategy version 'v1_rule_based'.
- Filtering by learner's current CI level (never pushes to higher CI level).
- Exclusion of recently watched items and items before latest deletion cutoff.
- Priority layers:
  1. continue_series: Next unwatched episode of a series currently in progress.
  2. preferred_topic: Unwatched items matching learner's preferred topics at same level.
  3. same_level: Unwatched items at learner's current CI level.
  4. editor_pick: Curated series items or published items at same level as fallback.
- Stable tie-breaker by catalog_item_id.
- Privacy & Pedagogy: No title_internal exposure, no vocabulary scores.
"""

from __future__ import annotations

from jplearn_api.application.ports.unit_of_work import AsyncUnitOfWork
from jplearn_api.application.queries import GetRecommendationsQuery
from jplearn_api.domain.recommendation import (
    RecommendationReason,
    RecommendedItemProjection,
)

STRATEGY_VERSION = "v1_rule_based"


async def handle_get_recommendations(
    query: GetRecommendationsQuery,
    uow: AsyncUnitOfWork,
) -> tuple[list[RecommendedItemProjection], str]:
    """Produce deterministic recommendations for learner."""
    limit = max(1, min(query.limit, 50))

    # 1. Learner context: CI level & preferences
    progress = await uow.learning.get_progress(query.user_id)
    learner_ci_level = progress.current_ci_level if progress is not None else 1

    prefs = await uow.playbacks.get_learning_preferences(query.user_id)
    preferred_topic_ids = set(prefs.preferred_topic_ids) if prefs else set()

    cutoff_time = await uow.playbacks.get_latest_history_deletion_cutoff(query.user_id)

    # 2. Watch history & resuming checkpoints (strictly isolated after cutoff)
    history_items, _ = await uow.playbacks.list_watch_history(
        user_id=query.user_id,
        cutoff_time=cutoff_time,
        limit=200,
    )
    watched_ids = {h.catalog_item_id for h in history_items}

    checkpoints, _ = await uow.playbacks.list_resume(user_id=query.user_id, limit=50)
    # Checkpoints updated after cutoff or without cutoff
    resuming_ids = set()
    for cp in checkpoints:
        cp_time = cp.updated_at.replace(tzinfo=None) if cp.updated_at.tzinfo else cp.updated_at
        if cutoff_time is None:
            resuming_ids.add(cp.catalog_item_id)
        else:
            c_time = cutoff_time.replace(tzinfo=None) if cutoff_time.tzinfo else cutoff_time
            if cp_time > c_time:
                resuming_ids.add(cp.catalog_item_id)

    active_watched_ids = watched_ids | resuming_ids

    # 3. Published series map
    published_series = await uow.series.list_published(limit=100)
    # Map item_id -> (series_id, series_title, position)
    item_series_info: dict[str, tuple[str, str, int]] = {}
    for s in published_series:
        for it in s.items:
            item_series_info[it.catalog_item_id] = (s.id, s.title, it.position)

    selected_ids: set[str] = set()
    recommendations: list[RecommendedItemProjection] = []

    async def get_title_jp(cat_id: str) -> str | None:
        """Safely fetch Japanese title from scenes, avoiding internal staff title."""
        try:
            ver = await uow.content.get_published_by_catalog_item_id(cat_id)
            if ver and ver.scenes:
                return ver.scenes[0].title_jp
        except Exception:
            pass
        return None

    # Priority 1: continue_series
    # Find series where learner has watched an episode, and recommend the next episode
    for s in published_series:
        if s.ci_level != str(learner_ci_level):
            continue
        sorted_items = sorted(s.items, key=lambda x: x.position)
        # Find highest watched position
        max_watched_pos = -1
        for it in sorted_items:
            if it.catalog_item_id in active_watched_ids:
                max_watched_pos = max(max_watched_pos, it.position)

        if max_watched_pos >= 0:
            next_unwatched = [
                it for it in sorted_items
                if it.position > max_watched_pos and it.catalog_item_id not in active_watched_ids
            ]
            if next_unwatched:
                target_it = next_unwatched[0]
                item_obj = await uow.catalog.get_by_id(target_it.catalog_item_id)
                if (
                    item_obj
                    and item_obj.status == "published"
                    and item_obj.ci_level == learner_ci_level
                    and item_obj.id not in selected_ids
                ):
                    title_jp = await get_title_jp(item_obj.id)
                    recommendations.append(
                        RecommendedItemProjection(
                            catalog_item_id=item_obj.id,
                            media_type=item_obj.media_type,
                            topic_id=item_obj.topic_id,
                            duration_seconds=item_obj.duration_seconds,
                            ci_level=item_obj.ci_level,
                            reason=RecommendationReason.CONTINUE_SERIES,
                            title_jp=title_jp,
                            series_id=s.id,
                            series_title=s.title,
                        )
                    )
                    selected_ids.add(item_obj.id)

    # 4. Published items at same CI level
    published_items = await uow.catalog.list_published(ci_level=learner_ci_level, limit=200)

    # Priority 2: preferred_topic
    preferred_candidates = [
        item for item in published_items
        if item.id not in selected_ids
        and item.id not in active_watched_ids
        and item.topic_id in preferred_topic_ids
    ]
    preferred_candidates.sort(key=lambda x: x.id)

    for item in preferred_candidates:
        if len(recommendations) >= limit:
            break
        s_info = item_series_info.get(item.id)
        title_jp = await get_title_jp(item.id)
        recommendations.append(
            RecommendedItemProjection(
                catalog_item_id=item.id,
                media_type=item.media_type,
                topic_id=item.topic_id,
                duration_seconds=item.duration_seconds,
                ci_level=item.ci_level,
                reason=RecommendationReason.PREFERRED_TOPIC,
                title_jp=title_jp,
                series_id=s_info[0] if s_info else None,
                series_title=s_info[1] if s_info else None,
            )
        )
        selected_ids.add(item.id)

    # Priority 3: same_level
    same_level_candidates = [
        item for item in published_items
        if item.id not in selected_ids
        and item.id not in active_watched_ids
    ]
    same_level_candidates.sort(key=lambda x: x.id)

    for item in same_level_candidates:
        if len(recommendations) >= limit:
            break
        s_info = item_series_info.get(item.id)
        title_jp = await get_title_jp(item.id)
        recommendations.append(
            RecommendedItemProjection(
                catalog_item_id=item.id,
                media_type=item.media_type,
                topic_id=item.topic_id,
                duration_seconds=item.duration_seconds,
                ci_level=item.ci_level,
                reason=RecommendationReason.SAME_LEVEL,
                title_jp=title_jp,
                series_id=s_info[0] if s_info else None,
                series_title=s_info[1] if s_info else None,
            )
        )
        selected_ids.add(item.id)

    # Priority 4: editor_pick (Fallback)
    if len(recommendations) < limit:
        editor_candidates = [
            item for item in published_items
            if item.id not in selected_ids
        ]
        editor_candidates.sort(key=lambda x: x.id)
        for item in editor_candidates:
            if len(recommendations) >= limit:
                break
            s_info = item_series_info.get(item.id)
            title_jp = await get_title_jp(item.id)
            recommendations.append(
                RecommendedItemProjection(
                    catalog_item_id=item.id,
                    media_type=item.media_type,
                    topic_id=item.topic_id,
                    duration_seconds=item.duration_seconds,
                    ci_level=item.ci_level,
                    reason=RecommendationReason.EDITOR_PICK,
                    title_jp=title_jp,
                    series_id=s_info[0] if s_info else None,
                    series_title=s_info[1] if s_info else None,
                )
            )
            selected_ids.add(item.id)

    return recommendations[:limit], STRATEGY_VERSION
