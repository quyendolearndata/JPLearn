from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import json
import logging
from typing import Any

import httpx

from jplearn_api.sanitizer import sanitize_message
from jplearn_api.settings import Settings

logger = logging.getLogger("jplearn_api.alert")

ALERT_QUEUE_MAX_SIZE = 1000
_global_alert_queue: asyncio.Queue[dict[str, Any]] | None = None


def get_alert_queue() -> asyncio.Queue[dict[str, Any]]:
    global _global_alert_queue
    if _global_alert_queue is None:
        _global_alert_queue = asyncio.Queue(maxsize=ALERT_QUEUE_MAX_SIZE)
    return _global_alert_queue


def enqueue_alert(
    settings: Settings,
    *,
    method: str,
    path: str,
    status: int,
    request_id: str,
    message: str,
    queue: asyncio.Queue[dict[str, Any]] | None = None,
) -> bool:
    """Non-blocking alert enqueueing. Never adds latency to the request lifecycle."""
    if not settings.alert_webhook_url:
        return False

    target_queue = queue if queue is not None else get_alert_queue()
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
        target_queue.put_nowait(payload)
        return True
    except asyncio.QueueFull:
        print(
            json.dumps({
                "alert_5xx": "queue_overflow",
                "request_id": request_id,
                "dropped": True,
            })
        )
        return False


async def _dispatch_one_alert(client: httpx.AsyncClient, url: str, payload: dict[str, Any]) -> None:
    request_id = payload.get("requestId", "unknown")
    try:
        response = await client.post(url, json=payload)
        if response.status_code >= 400:
            print(
                json.dumps({
                    "alert_5xx": "webhook_rejected",
                    "webhook_status": response.status_code,
                    "request_id": request_id,
                })
            )
    except Exception as error:
        safe_error = sanitize_message(str(error))[:100]
        print(
            json.dumps({
                "alert_5xx": "webhook_failed",
                "error": safe_error,
                "request_id": request_id,
            })
        )


async def alert_worker(queue: asyncio.Queue[dict[str, Any]], settings: Settings) -> None:
    """Background consumer task for alerts."""
    url = settings.alert_webhook_url
    if not url:
        while True:
            try:
                await queue.get()
                queue.task_done()
            except asyncio.CancelledError:
                break
        return

    async with httpx.AsyncClient(timeout=1.0) as client:
        while True:
            try:
                payload = await queue.get()
            except asyncio.CancelledError:
                break

            try:
                await _dispatch_one_alert(client, url, payload)
            except Exception as exc:
                logger.error(f"Unexpected error in alert worker: {exc}")
            finally:
                queue.task_done()


async def drain_alert_queue(
    queue: asyncio.Queue[dict[str, Any]],
    worker_task: asyncio.Task[None] | None,
    timeout: float = 3.0,
) -> None:
    """Drain pending alerts on application shutdown with a strict deadline."""
    if worker_task is None or worker_task.done():
        return

    try:
        await asyncio.wait_for(queue.join(), timeout=timeout)
    except asyncio.TimeoutError:
        print(json.dumps({"alert_5xx": "drain_timeout", "pending": queue.qsize()}))
    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass


async def send_alert_5xx(
    settings: Settings,
    *,
    method: str,
    path: str,
    status: int,
    request_id: str,
    message: str,
    queue: asyncio.Queue[dict[str, Any]] | None = None,
) -> None:
    """Backward-compatible async wrapper around enqueue_alert."""
    enqueue_alert(
        settings,
        method=method,
        path=path,
        status=status,
        request_id=request_id,
        message=message,
        queue=queue,
    )
