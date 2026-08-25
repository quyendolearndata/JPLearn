"use client";

import { useState } from "react";
import type { CatalogItemPublic } from "@jplearn/domain";
import { api } from "../../lib/api";
import { getToken } from "../../lib/auth-storage";

export default function SessionPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [clipUrl, setClipUrl] = useState<string | null>(null);

  async function start() {
    const token = getToken();
    if (!token) {
      setStatus("Hãy đăng nhập.");
      return;
    }
    const res = await api("/sessions", {
      method: "POST",
      token,
      body: JSON.stringify({ device_class: "web" }),
    });
    const body = await res.json();
    setSessionId(body.id);
    const catalog = await api("/catalog", { token }).then((r) => r.json()) as {
      items: CatalogItemPublic[];
    };
    const clip = catalog.items.find((item) => item.playback_url);
    setClipUrl(clip?.playback_url ?? null);
    setStatus(clip?.playback_url ? "Phiên đang chạy." : "Phiên đang chạy. Chưa có clip published.");
  }

  async function end() {
    const token = getToken();
    if (!token || !sessionId) return;
    await api(`/sessions/${sessionId}/end`, { method: "POST", token });
    setSessionId(null);
    setClipUrl(null);
    setStatus("Đã kết thúc phiên.");
  }

  return (
    <section>
      <h1>Phiên</h1>
      <p>{status}</p>
      <button type="button" onClick={() => void start()}>
        Bắt đầu phiên
      </button>
      <button type="button" onClick={() => void end()}>
        Kết thúc phiên
      </button>
      {clipUrl ? (
        <video src={clipUrl} controls playsInline style={{ width: "100%", maxWidth: 720, marginTop: 16 }} />
      ) : null}
    </section>
  );
}
