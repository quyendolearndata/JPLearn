"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import type { CatalogItemPublic } from "@jplearn/domain";
import { api, parseApiError, parseApiResponse } from "../../lib/api";
import { getToken, getUser } from "../../lib/auth-storage";
import { CiPlayer } from "../../components/ci-player";
import {
  clearSessionRecord,
  newIdempotencyKey,
  readSessionRecord,
  writeSessionRecord,
  type StoredSession,
} from "../../lib/session-storage";

function currentUserId(): string | null {
  return getUser()?.id ?? null;
}

interface EndSummary {
  minutesComprehensible: number;
  currentCiLevel: number;
  durationSeconds: number;
}

const TOPIC_NAMES: Record<string, string> = {
  daily_home: "Sinh hoạt gia đình",
  food: "Ẩm thực & Nấu ăn",
  shopping: "Mua sắm & Cửa hàng",
  travel: "Du lịch & Phương tiện",
  nature: "Thiên nhiên & Đời sống",
  culture: "Văn hoá Nhật Bản",
  body: "Cơ thể & Sức khoẻ",
  work: "Công việc & Xã hội",
};

function SessionContent() {
  const searchParams = useSearchParams();
  const requestedItemId = searchParams.get("item_id");

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("");
  const [clip, setClip] = useState<CatalogItemPublic | null>(null);
  const [startedAt, setStartedAt] = useState<Date | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [loading, setLoading] = useState(false);
  const [completedSummary, setCompletedSummary] = useState<EndSummary | null>(null);

  const pendingIdempotencyKeyRef = useRef<string | null>(null);

  const loadClip = useCallback(async (targetItemId?: string | null) => {
    const token = getToken();
    if (!token) return;
    let playable: CatalogItemPublic | null = null;
    try {
      const catRes = await api("/catalog", { token });
      if (catRes.ok) {
        const catalog = await parseApiResponse<{ items: CatalogItemPublic[] }>(catRes);
        const items = catalog?.items || [];
        if (targetItemId) playable = items.find((i) => i.id === targetItemId) || null;
        if (!playable && items.length > 0) playable = items.find((i) => i.hls_url ?? i.playback_url) || items[0];
      }
    } catch {
      /* catalog failure must not block end-session */
    }
    setClip(playable);
    setStatus(playable ? "Phiên đang chạy." : "Phiên đang chạy. Chưa có clip published.");
  }, []);

  // Check and recover session from scoped sessionStorage
  const checkActiveSession = useCallback(async () => {
    const token = getToken();
    const userId = currentUserId();
    if (!token || !userId) return;
    try { localStorage.removeItem("jplearn_active_session"); } catch {}

    const stored = readSessionRecord(userId);
    if (!stored) return;

    // 1. Mid-flight start: replay POST with the same key.
    if (stored.state === "starting") {
      setStatus("Đang khôi phục phiên...");
      setLoading(true);
      try {
        const res = await api("/sessions", {
          method: "POST",
          token,
          headers: { "Idempotency-Key": stored.idempotencyKey },
          body: JSON.stringify({ device_class: stored.deviceClass }),
        });
        if (res.ok) {
          const body = await parseApiResponse<{ id: string; started_at?: string }>(res);
          if (body?.id) {
            const active: StoredSession = { ...stored, state: "active", sessionId: body.id, startedAt: body.started_at || stored.startedAt };
            writeSessionRecord(userId, active);
            setSessionId(body.id);
            setStartedAt(new Date(active.startedAt));
            await loadClip(stored.itemId);
            setStatus("Phiên đang chạy (đã khôi phục).");
            return;
          }
        }
        clearSessionRecord(userId);
        setStatus("Không thể khôi phục phiên.");
      } catch {
        setStatus("Lỗi kết nối khi khôi phục phiên. Tải lại trang để thử lại.");
      } finally {
        setLoading(false);
      }
      return;
    }

    if (!stored.sessionId) { clearSessionRecord(userId); return; }

    // 2. active / ending / outcome_unknown: ask the server what really happened.
    try {
      const res = await api(`/sessions/${stored.sessionId}`, { token });
      if (res.status === 404 || res.status === 403) { clearSessionRecord(userId); return; }
      if (!res.ok) throw new Error("status check failed");
      const data = await parseApiResponse<{ started_at?: string; ended_at?: string | null; duration_seconds?: number }>(res);

      if (data?.ended_at) {
        clearSessionRecord(userId);
        if (stored.state === "ending" || stored.state === "outcome_unknown") {
          const progressRes = await api("/progress", { token });
          const progress = progressRes.ok
            ? await parseApiResponse<{ minutes_comprehensible: number; current_ci_level: number }>(progressRes)
            : null;
          setCompletedSummary({
            minutesComprehensible: progress?.minutes_comprehensible ?? 0,
            currentCiLevel: progress?.current_ci_level ?? 0,
            durationSeconds: data.duration_seconds ?? 0,
          });
          setStatus("Phiên đã kết thúc.");
        }
        return;
      }

      // Still active on the server.
      const start = new Date(data?.started_at || stored.startedAt);
      setSessionId(stored.sessionId);
      setStartedAt(start);
      setElapsedSeconds(Math.max(0, Math.floor((Date.now() - start.getTime()) / 1000)));
      writeSessionRecord(userId, { ...stored, state: "active" });
      setStatus(stored.state === "active" ? "Phiên đang chạy." : "Phiên vẫn đang chạy trên máy chủ — hãy kết thúc lại.");
      await loadClip(stored.itemId);
    } catch {
      if (stored.state !== "active") {
        writeSessionRecord(userId, { ...stored, state: "outcome_unknown" });
        setStatus("Chưa xác nhận được trạng thái phiên với máy chủ. Tải lại trang khi có mạng.");
      } else {
        setStatus("Không kiểm tra được phiên với máy chủ.");
      }
    }
  }, [loadClip]);

  useEffect(() => {
    void checkActiveSession();
  }, [checkActiveSession]);

  // Elapsed timer ticker while session is active
  useEffect(() => {
    if (!sessionId || !startedAt) return;

    const interval = setInterval(() => {
      const now = Date.now();
      const elapsed = Math.max(0, Math.floor((now - startedAt.getTime()) / 1000));
      setElapsedSeconds(elapsed);
    }, 1000);

    return () => clearInterval(interval);
  }, [sessionId, startedAt]);

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  // Start learning session with Idempotency-Key
  const startSession = async () => {
    const token = getToken();
    const userId = currentUserId();
    if (!token || !userId) {
      setStatus("Hãy đăng nhập.");
      return;
    }

    setLoading(true);
    setCompletedSummary(null);

    const idempotencyKey = pendingIdempotencyKeyRef.current || newIdempotencyKey();
    pendingIdempotencyKeyRef.current = idempotencyKey;

    const startedAtIso = new Date().toISOString();

    // Persist "starting" state BEFORE sending POST /sessions
    const startingRecord: StoredSession = {
      v: 1,
      state: "starting",
      idempotencyKey,
      startedAt: startedAtIso,
      itemId: requestedItemId || undefined,
      deviceClass: "web",
    };
    writeSessionRecord(userId, startingRecord);

    try {
      const res = await api("/sessions", {
        method: "POST",
        token,
        headers: {
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify({ device_class: "web" }),
      });

      if (!res.ok) {
        clearSessionRecord(userId);
        const err = await parseApiError(res);
        setStatus(err.message || "Không thể bắt đầu phiên.");
        return;
      }

      const body = await parseApiResponse<{ id: string; started_at?: string }>(res);
      if (!body?.id) {
        clearSessionRecord(userId);
        setStatus("Dữ liệu phiên không hợp lệ.");
        return;
      }

      // IMMEDIATELY update sessionStorage to "active" BEFORE fetching catalog
      const activeRecord: StoredSession = {
        v: 1,
        state: "active",
        sessionId: body.id,
        itemId: requestedItemId || undefined,
        idempotencyKey,
        startedAt: body.started_at || startedAtIso,
        deviceClass: "web",
      };
      writeSessionRecord(userId, activeRecord);

      const start = new Date(activeRecord.startedAt);
      setSessionId(body.id);
      setStartedAt(start);
      setElapsedSeconds(0);
      pendingIdempotencyKeyRef.current = null;

      await loadClip(requestedItemId);
    } catch {
      // Keep "starting" in storage so reload can recover using same idempotency key
      setStatus("Lỗi kết nối máy chủ khi bắt đầu phiên.");
    } finally {
      setLoading(false);
    }
  };

  // End learning session
  const endSession = async () => {
    const token = getToken();
    const userId = currentUserId();
    if (!token || !sessionId || !userId) return;

    const rec = readSessionRecord(userId);
    if (rec) writeSessionRecord(userId, { ...rec, state: "ending" });

    setLoading(true);
    try {
      const res = await api(`/sessions/${sessionId}/end`, {
        method: "POST",
        token,
      });

      if (!res.ok) {
        const latest = readSessionRecord(userId);
        if (latest) writeSessionRecord(userId, { ...latest, state: "outcome_unknown" });

        const checkRes = await api(`/sessions/${sessionId}`, { token });
        if (checkRes.ok) {
          const checkData = await parseApiResponse<{ ended_at?: string; duration_seconds?: number }>(checkRes);
          if (checkData?.ended_at) {
            clearSessionRecord(userId);
            const progressRes = await api("/progress", { token });
            const progress = progressRes.ok
              ? await parseApiResponse<{
                  minutes_comprehensible: number;
                  current_ci_level: number;
                }>(progressRes)
              : null;
            setCompletedSummary({
              minutesComprehensible: progress?.minutes_comprehensible ?? 0,
              currentCiLevel: progress?.current_ci_level ?? 0,
              durationSeconds: checkData.duration_seconds ?? elapsedSeconds,
            });
            setSessionId(null);
            setClip(null);
            setStatus("Đã kết thúc phiên.");
            return;
          }
        }
        const err = await parseApiError(res);
        setStatus(err.message || "Không thể kết thúc phiên. Vui lòng thử lại.");
        return;
      }

      const progress = await parseApiResponse<{
        minutes_comprehensible: number;
        current_ci_level: number;
      }>(res);

      clearSessionRecord(userId);
      setCompletedSummary({
        minutesComprehensible: progress?.minutes_comprehensible ?? 0,
        currentCiLevel: progress?.current_ci_level ?? 0,
        durationSeconds: elapsedSeconds,
      });
      setSessionId(null);
      setClip(null);
      setStatus("Đã kết thúc phiên.");
    } catch {
      const latest = readSessionRecord(userId);
      if (latest) writeSessionRecord(userId, { ...latest, state: "outcome_unknown" });
      try {
        const checkRes = await api(`/sessions/${sessionId}`, { token });
        if (checkRes.ok) {
          const checkData = await parseApiResponse<{ ended_at?: string }>(checkRes);
          if (checkData?.ended_at) {
            clearSessionRecord(userId);
            setSessionId(null);
            setClip(null);
            setStatus("Đã kết thúc phiên.");
            return;
          }
        }
      } catch {}
      setStatus("Lỗi kết nối khi kết thúc phiên.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="login-card" style={{ maxWidth: "720px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: "0.5rem" }}>
        <h1>Phiên</h1>
        {sessionId && (
          <div style={{ fontWeight: 800, fontSize: "1.1rem", color: "var(--pink)" }}>
            ⏱ {formatTime(elapsedSeconds)}
          </div>
        )}
      </div>

      <p className="status-text" style={{ marginTop: "0.5rem", fontWeight: 700, color: sessionId ? "#15803d" : "var(--charcoal)" }}>
        {status}
      </p>

      {clip ? (
        <div style={{ marginTop: "1.5rem", marginBottom: "1.5rem" }}>
          <div style={{ borderRadius: "var(--radius-md)", overflow: "hidden", border: "2px solid var(--charcoal)", background: "#000000" }}>
            <CiPlayer hlsUrl={clip.hls_url} playbackUrl={clip.playback_url} />
          </div>
          <div style={{ marginTop: "0.75rem", display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap", fontSize: "0.85rem", color: "var(--text-muted)", fontWeight: 700 }}>
            <span>Chủ đề: {TOPIC_NAMES[clip.topic_id] || clip.topic_id}</span>
            <span>·</span>
            <span>Cấp độ CI {clip.ci_level}</span>
            <span>·</span>
            <span>{clip.duration_seconds} giây</span>
          </div>
        </div>
      ) : null}

      {completedSummary && (
        <div style={{ background: "var(--bg-subtle)", border: "1.5px solid var(--charcoal)", borderRadius: "var(--radius-sm)", padding: "1.25rem", margin: "1.5rem 0" }}>
          <h2 style={{ fontSize: "1.2rem", fontWeight: 900, marginBottom: "0.5rem" }}>
            Tổng kết phiên học
          </h2>
          <p style={{ margin: "0.25rem 0" }}>
            Thời lượng: <strong>{formatTime(completedSummary.durationSeconds)}</strong>
          </p>
          <p style={{ margin: "0.25rem 0" }}>
            Tổng tích luỹ: <strong>{completedSummary.minutesComprehensible} phút</strong>
          </p>
          <p style={{ margin: "0.25rem 0" }}>
            Cấp độ CI: <strong>Cấp {completedSummary.currentCiLevel}</strong>
          </p>
          <div style={{ marginTop: "1rem", display: "flex", gap: "0.75rem" }}>
            <Link href="/catalog" className="btn-cta btn-secondary" style={{ fontSize: "0.85rem", padding: "0.4rem 0.8rem" }}>
              Xem Catalog
            </Link>
            <Link href="/progress" className="btn-cta btn-secondary" style={{ fontSize: "0.85rem", padding: "0.4rem 0.8rem" }}>
              Xem Tiến độ
            </Link>
          </div>
        </div>
      )}

      <div className="button-group">
        <button
          type="button"
          onClick={() => void startSession()}
          disabled={loading || Boolean(sessionId)}
          className="btn-primary"
        >
          {loading && !sessionId ? "Đang xử lý…" : "Bắt đầu phiên"}
        </button>
        <button
          type="button"
          onClick={() => void endSession()}
          disabled={loading || !sessionId}
          className="btn-danger"
        >
          {loading && sessionId ? "Đang xử lý…" : "Kết thúc phiên"}
        </button>
      </div>
    </section>
  );
}

export default function SessionPage() {
  return (
    <Suspense fallback={<section><h1>Phiên</h1><p>Đang tải…</p></section>}>
      <SessionContent />
    </Suspense>
  );
}
