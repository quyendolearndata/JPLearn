"use client";

import { catalogWriteFields } from "@jplearn/cms-schema";
import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { getToken, getUser } from "../../lib/auth-storage";

const TOPICS = [
  "daily_home",
  "food",
  "body",
  "go_somewhere",
  "nature",
  "people",
];

export default function StaffPage() {
  const [allowed, setAllowed] = useState(false);
  const [itemId, setItemId] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [topicId, setTopicId] = useState("daily_home");
  const [ciLevel, setCiLevel] = useState(0);
  const [duration, setDuration] = useState(30);
  const [mediaType, setMediaType] = useState<"video" | "audio">("video");
  const [visual, setVisual] = useState<"high" | "medium" | "low">("high");
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);

  useEffect(() => {
    const user = getUser();
    setAllowed(Boolean(user?.roles.includes("teacher") || user?.roles.includes("admin")));
  }, []);

  if (!allowed) {
    return (
      <section>
        <h1>Staff</h1>
        <p>403 — cần vai trò teacher hoặc admin.</p>
      </section>
    );
  }

  const token = getToken();
  const isAdmin = Boolean(getUser()?.roles.includes("admin"));

  async function create() {
    if (!token) return;
    const body: Record<string, string | number> = {
      topic_id: topicId,
      ci_level: ciLevel,
      duration_seconds: duration,
      media_type: mediaType,
      visual_support: visual,
      title_internal: title,
    };
    for (const field of catalogWriteFields) {
      if (!(field in body)) return;
    }
    const res = await api("/staff/catalog", {
      method: "POST",
      token,
      body: JSON.stringify(body),
    });
    const item = await res.json();
    setItemId(item.id);
    setStatus(`Draft ${item.id}`);
    if (file && item.id) {
      const form = new FormData();
      form.append("file", file);
      await api(`/staff/catalog/${item.id}/media`, { method: "POST", token, body: form });
    }
  }

  async function submitQa() {
    if (!token || !itemId) return;
    await api(`/staff/catalog/${itemId}/submit-qa`, { method: "POST", token });
    setStatus("level_qa");
  }

  async function publish() {
    if (!token || !itemId) return;
    await api(`/staff/catalog/${itemId}/publish`, { method: "POST", token });
    setStatus("published");
  }

  return (
    <section>
      <h1>Staff CMS</h1>
      <p>{status}</p>
      <label htmlFor="topic">topic_id</label>
      <select id="topic" value={topicId} onChange={(e) => setTopicId(e.target.value)}>
        {TOPICS.map((id) => (
          <option key={id} value={id}>
            {id}
          </option>
        ))}
      </select>
      <label htmlFor="ci">ci_level</label>
      <input
        id="ci"
        type="number"
        min={0}
        max={4}
        value={ciLevel}
        onChange={(e) => setCiLevel(Number(e.target.value))}
      />
      <label htmlFor="dur">duration_seconds</label>
      <input
        id="dur"
        type="number"
        min={1}
        value={duration}
        onChange={(e) => setDuration(Number(e.target.value))}
      />
      <label htmlFor="mt">media_type</label>
      <select
        id="mt"
        value={mediaType}
        onChange={(e) => setMediaType(e.target.value as "video" | "audio")}
      >
        <option value="video">video</option>
        <option value="audio">audio</option>
      </select>
      <label htmlFor="vs">visual_support</label>
      <select
        id="vs"
        value={visual}
        onChange={(e) => setVisual(e.target.value as "high" | "medium" | "low")}
      >
        <option value="high">high</option>
        <option value="medium">medium</option>
        <option value="low">low</option>
      </select>
      <label htmlFor="title">title_internal</label>
      <input id="title" value={title} onChange={(e) => setTitle(e.target.value)} />
      <label htmlFor="file">file</label>
      <input id="file" type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      <button type="button" onClick={() => void create()}>
        Tạo draft
      </button>
      <button type="button" onClick={() => void submitQa()}>
        Nộp QA
      </button>
      {isAdmin ? (
        <button type="button" onClick={() => void publish()}>
          Publish
        </button>
      ) : null}
    </section>
  );
}
