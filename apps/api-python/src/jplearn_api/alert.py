from datetime import UTC, datetime

import httpx

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
    clipped = message[:300]
    payload = {
        "text": f"[JPLearn API] {status} {method} {path} — {clipped} (requestId={request_id})",
        "method": method,
        "path": path,
        "status": status,
        "requestId": request_id,
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "message": clipped,
    }
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code >= 400:
                print(
                    '{"alert_5xx":"webhook_rejected",'
                    f'"webhook_status":{response.status_code},"request_id":"{request_id}"}}',
                )
    except Exception as error:
        print(
            '{"alert_5xx":"webhook_failed",'
            f'"error":"{error}","request_id":"{request_id}"}}',
        )
