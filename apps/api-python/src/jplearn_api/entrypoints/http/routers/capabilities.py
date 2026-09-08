from fastapi import APIRouter, Depends

from jplearn_api.application.read_models import UserDTO
from jplearn_api.entrypoints.http.dependencies import get_app_settings
from jplearn_api.entrypoints.http.schemas import Capabilities
from jplearn_api.entrypoints.http.security import require_user
from jplearn_api.settings import Settings

router = APIRouter(tags=["Capabilities"])


@router.get(
    "/capabilities",
    response_model=Capabilities,
    operation_id="getCapabilities",
    openapi_extra={"x-jplearn-fr": ["FR-FLG-001"]},
)
async def read_capabilities(
    settings: Settings = Depends(get_app_settings),
    _user: UserDTO = Depends(require_user),
) -> Capabilities:
    return Capabilities(
        video_scene_breakdown_enabled=settings.video_scene_breakdown_enabled,
        smart_stream_enabled=settings.smart_stream_enabled,
        interactive_dual_subs_enabled=settings.interactive_dual_subs_enabled,
        immersion_lookup_enabled=settings.immersion_lookup_enabled,
        personal_collections_enabled=settings.personal_collections_enabled,
        content_reports_enabled=settings.content_reports_enabled,
        playback_tracking_enabled=settings.playback_tracking_enabled,
        scene_search_enabled=settings.scene_search_enabled,
        staff_ai_enabled=settings.staff_ai_enabled,
    )
