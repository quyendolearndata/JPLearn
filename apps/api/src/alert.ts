// NFR-OBS-001: alert 5xx thật trên staging qua webhook stub.
// Default TẮT (quy ước flags default false): chỉ gọi khi ALERT_WEBHOOK_URL được set.
// Payload có `text` tóm tắt nên tương thích Slack incoming webhook.
export interface Alert5xx {
  method: string;
  path: string;
  status: number;
  requestId: string;
  message: string;
}

export async function sendAlert5xx(alert: Alert5xx): Promise<void> {
  const url = process.env.ALERT_WEBHOOK_URL;
  if (!url) return;
  const message = alert.message.slice(0, 300);
  const payload = {
    text: `[JPLearn API] ${alert.status} ${alert.method} ${alert.path} — ${message} (requestId=${alert.requestId})`,
    method: alert.method,
    path: alert.path,
    status: alert.status,
    requestId: alert.requestId,
    timestamp: new Date().toISOString(),
    message,
  };
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(2_000),
    });
    if (!res.ok) {
      console.warn(
        JSON.stringify({
          alert_5xx: "webhook_rejected",
          webhook_status: res.status,
          request_id: alert.requestId,
        }),
      );
    }
  } catch (err) {
    console.warn(
      JSON.stringify({
        alert_5xx: "webhook_failed",
        error: err instanceof Error ? err.message : String(err),
        request_id: alert.requestId,
      }),
    );
  }
}
