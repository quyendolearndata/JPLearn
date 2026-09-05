"""Re-export alerts adapter for backward compatibility."""

from jplearn_api.adapters.observability.alerts import (
    ALERT_QUEUE_MAX_SIZE,
    alert_worker,
    drain_alert_queue,
    enqueue_alert,
    get_alert_queue,
    logger,
    send_alert_5xx,
)

__all__ = [
    "ALERT_QUEUE_MAX_SIZE",
    "alert_worker",
    "drain_alert_queue",
    "enqueue_alert",
    "get_alert_queue",
    "logger",
    "send_alert_5xx",
]
