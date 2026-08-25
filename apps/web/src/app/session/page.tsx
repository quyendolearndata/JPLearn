"use client";

import { useState } from "react";
import { api } from "../../lib/api";
import { getToken } from "../../lib/auth-storage";

export default function SessionPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState("");

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
    setStatus("Phiên đang chạy.");
  }

  async function end() {
    const token = getToken();
    if (!token || !sessionId) return;
    await api(`/sessions/${sessionId}/end`, { method: "POST", token });
    setSessionId(null);
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
    </section>
  );
}
