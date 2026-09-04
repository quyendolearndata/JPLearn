from datetime import UTC, datetime

import httpx

from jplearn_api.sanitizer import sanitize_message
from jplearn_api.settings import Settings


async def send_alert_5xx(
    settings: Settings,
    *,
    method: str,
    path: str,
    status: int,
    request_id: str,
    message: str,
) -> None:
    url = settings.alert_webhook_url
    if not url:
        return
    sanitized = sanitize_message(message)[:300]
    payload = {
        "text": f"[JPLearn API] {status} {method} {path} — {sanitized} (requestId={request_id})",
        "method": method,
        "path": path,
        "status": status,
        "requestId": request_id,
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "message": sanitized,
    }
    try:
        async with httpx.AsyncClient(timeout=0.5) as client:
            response = await client.post(url, json=payload)
            if response.status_code >= 400:
                print(
                    '{"alert_5xx":"webhook_rejected",'
                    f'"webhook_status":{response.status_code},"request_id":"{request_id}"}}',
                )
    except Exception as error:
        safe_error = sanitize_message(str(error))[:100]
        print(
            '{"alert_5xx":"webhook_failed",'
            f'"error":"{safe_error}","request_id":"{request_id}"}}',
        )
