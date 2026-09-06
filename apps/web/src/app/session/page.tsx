"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import type { CatalogItemPublic } from "@jplearn/domain";
import { api, parseApiError, parseApiResponse } from "../../lib/api";
import { getToken, getUser } from "../../lib/auth-storage";
import { CiPlayer } from "../../components/ci-player";
import {
  classifyReplayFailure,
  isLearningSessionResponse,
} from "../../lib/session-recovery";
import {
  clearSessionRecord,
  newIdempotencyKey,
  readSessionRecord,
  recoveryRequestFor,
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

type RecoveryPhase = "initializing" | "verifying" | "ready" | "unverified";

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
  const [status, setStatus] = useState<string>("Đang kiểm tra phiên...");
  const [clip, setClip] = useState<CatalogItemPublic | null>(null);
  const [startedAt, setStartedAt] = useState<Date | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [loading, setLoading] = useState(false);
  const [completedSummary, setCompletedSummary] = useState<EndSummary | null>(null);
  const [recoveryPhase, setRecoveryPhase] = useState<RecoveryPhase>("initializing");

  const recoveryAttemptRef = useRef(0);
  const recoveryInFlightRef = useRef(false);
  const recoveryAbortRef = useRef<AbortController | null>(null);

  const loadClip = useCallback(async (
    targetItemId?: string | null,
    shouldApply: () => boolean = () => true,
  ) => {
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
    if (!shouldApply()) return;
    setClip(playable);
    setStatus(playable ? "Phiên đang chạy." : "Phiên đang chạy. Chưa có clip published.");
  }, []);

  // Check and recover session from scoped sessionStorage
  const checkActiveSession = useCallback(async () => {
    if (recoveryInFlightRef.current) return;

    const token = getToken();
    const userId = currentUserId();
    const attempt = ++recoveryAttemptRef.current;
    const isCurrentAttempt = () =>
      recoveryAttemptRef.current === attempt && currentUserId() === userId;

    if (!token || !userId) {
      setRecoveryPhase("ready");
      setStatus("");
      return;
    }
    try { localStorage.removeItem("jplearn_active_session"); } catch {}

    const stored = readSessionRecord(userId);
    if (!stored) {
      setRecoveryPhase("ready");
      setStatus("");
      return;
    }

    const recoveryRequest = recoveryRequestFor(stored);
    if (!recoveryRequest) {
      clearSessionRecord(userId);
      setStatus("Dữ liệu khôi phục phiên không hợp lệ.");
      setRecoveryPhase("ready");
      return;
    }

    recoveryInFlightRef.current = true;
    recoveryAbortRef.current = new AbortController();
    setRecoveryPhase("verifying");
    setStatus("Đang khôi phục phiên...");

    try {
      // 1. Mid-flight start: replay POST with the persisted request details.
      if (recoveryRequest.kind === "replay_start") {
        const res = await api("/sessions", {
          method: "POST",
          token,
          headers: { "Idempotency-Key": recoveryRequest.idempotencyKey },
          body: JSON.stringify({ device_class: recoveryRequest.deviceClass }),
          signal: recoveryAbortRef.current.signal,
        });

        if (!isCurrentAttempt()) return;
        if (!res.ok) {
          const disposition = classifyReplayFailure(res.status);
          if (disposition === "auth") return;
          if (disposition === "terminal") {
            clearSessionRecord(userId);
            setSessionId(null);
            setStartedAt(null);
            setClip(null);
            setStatus("Không thể khôi phục phiên do khóa chống trùng bị xung đột.");
            setRecoveryPhase("ready");
            return;
          }
          const err = await parseApiError(res);
          if (!isCurrentAttempt()) return;
          setStatus(err.message || "Không thể khôi phục phiên.");
          setRecoveryPhase("unverified");
          return;
        }

        const body = await parseApiResponse<unknown>(res);
        if (!isCurrentAttempt()) return;
        if (!isLearningSessionResponse(body)) {
          setStatus("Dữ liệu phiên không hợp lệ.");
          setRecoveryPhase("unverified");
          return;
        }

        if (body.ended_at) {
          clearSessionRecord(userId);
          setSessionId(null);
          setStartedAt(null);
          setClip(null);
          setStatus("Phiên đã kết thúc.");
          setRecoveryPhase("ready");
          return;
        }

        const active: StoredSession = {
          ...stored,
          state: "active",
          sessionId: body.id,
          startedAt: body.started_at,
        };
        writeSessionRecord(userId, active);
        setSessionId(body.id);
        setStartedAt(new Date(active.startedAt));
        setElapsedSeconds(Math.max(0, Math.floor((Date.now() - new Date(active.startedAt).getTime()) / 1000)));
        await loadClip(recoveryRequest.itemId, isCurrentAttempt);
        if (!isCurrentAttempt()) return;
        setStatus("Phiên đang chạy (đã khôi phục).");
        setRecoveryPhase("ready");
        return;
      }

      // 2. active / ending / outcome_unknown: ask the server what really happened.
      const res = await api(`/sessions/${recoveryRequest.sessionId}`, {
        token,
        signal: recoveryAbortRef.current.signal,
      });
      if (!isCurrentAttempt()) return;
      if (res.status === 401) return;
      if (res.status === 403 || res.status === 404) {
        clearSessionRecord(userId);
        setSessionId(null);
        setStartedAt(null);
        setClip(null);
        setStatus(
          res.status === 403
            ? "Bạn không có quyền khôi phục phiên này."
            : "Phiên cần khôi phục không còn tồn tại.",
        );
        setRecoveryPhase("ready");
        return;
      }
      if (!res.ok) {
        const err = await parseApiError(res);
        if (!isCurrentAttempt()) return;
        setStatus(err.message || "Không kiểm tra được phiên với máy chủ.");
        setRecoveryPhase("unverified");
        return;
      }

      const data = await parseApiResponse<unknown>(res);
      if (!isCurrentAttempt()) return;
      if (!isLearningSessionResponse(data, recoveryRequest.sessionId)) {
        setStatus("Dữ liệu phiên không hợp lệ.");
        setRecoveryPhase("unverified");
        return;
      }

      if (data.ended_at) {
        clearSessionRecord(userId);
        setSessionId(null);
        setStartedAt(null);
        setClip(null);
        if (stored.state === "ending" || stored.state === "outcome_unknown") {
          const progressRes = await api("/progress", { token });
          if (!isCurrentAttempt()) return;
          const progress = progressRes.ok
            ? await parseApiResponse<{ minutes_comprehensible: number; current_ci_level: number }>(progressRes)
            : null;
          if (!isCurrentAttempt()) return;
          setCompletedSummary({
            minutesComprehensible: progress?.minutes_comprehensible ?? 0,
            currentCiLevel: progress?.current_ci_level ?? 0,
            durationSeconds: data.duration_seconds ?? 0,
          });
        }
        setStatus("Phiên đã kết thúc.");
        setRecoveryPhase("ready");
        return;
      }

      // Still active on the server.
      const start = new Date(data.started_at);
      setSessionId(recoveryRequest.sessionId);
      setStartedAt(start);
      setElapsedSeconds(Math.max(0, Math.floor((Date.now() - start.getTime()) / 1000)));
      writeSessionRecord(userId, { ...stored, state: "active" });
      await loadClip(recoveryRequest.itemId, isCurrentAttempt);
      if (!isCurrentAttempt()) return;
      setStatus(stored.state === "active" ? "Phiên đang chạy." : "Phiên vẫn đang chạy trên máy chủ — hãy kết thúc lại.");
      setRecoveryPhase("ready");
    } catch {
      if (!isCurrentAttempt()) return;
      setStatus("Chưa xác nhận được trạng thái phiên với máy chủ.");
      setRecoveryPhase("unverified");
    } finally {
      if (recoveryAttemptRef.current === attempt) {
        recoveryInFlightRef.current = false;
        recoveryAbortRef.current = null;
      }
    }
  }, [loadClip]);

  useEffect(() => {
    void checkActiveSession();
    return () => {
      recoveryAttemptRef.current += 1;
      recoveryInFlightRef.current = false;
      recoveryAbortRef.current?.abort();
      recoveryAbortRef.current = null;
    };
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
    if (recoveryPhase !== "ready" || loading || sessionId) return;

    const token = getToken();
    const userId = currentUserId();
    if (!token || !userId) {
      setStatus("Hãy đăng nhập.");
      return;
    }

    if (readSessionRecord(userId)) {
      setRecoveryPhase("unverified");
      setStatus("Cần khôi phục phiên đã lưu trước khi bắt đầu phiên mới.");
      return;
    }

    setLoading(true);
    setCompletedSummary(null);

    const idempotencyKey = newIdempotencyKey();
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
        const disposition = classifyReplayFailure(res.status);
        if (disposition === "auth") return;
        if (disposition === "terminal") {
          clearSessionRecord(userId);
          setStatus("Không thể bắt đầu phiên do khóa chống trùng bị xung đột.");
          setRecoveryPhase("ready");
          return;
        }
        const err = await parseApiError(res);
        setStatus(err.message || "Không thể bắt đầu phiên.");
        setRecoveryPhase("unverified");
        return;
      }

      const body = await parseApiResponse<unknown>(res);
      if (!isLearningSessionResponse(body)) {
        setStatus("Dữ liệu phiên không hợp lệ.");
        setRecoveryPhase("unverified");
        return;
      }

      // IMMEDIATELY update sessionStorage to "active" BEFORE fetching catalog
      const activeRecord: StoredSession = {
        v: 1,
        state: "active",
        sessionId: body.id,
        itemId: requestedItemId || undefined,
        idempotencyKey,
        startedAt: body.started_at,
        deviceClass: "web",
      };
      writeSessionRecord(userId, activeRecord);

      const start = new Date(activeRecord.startedAt);
      setSessionId(body.id);
      setStartedAt(start);
      setElapsedSeconds(0);

      await loadClip(requestedItemId);
    } catch {
      // Keep "starting" in storage so reload can recover using same idempotency key
      setStatus("Lỗi kết nối máy chủ khi bắt đầu phiên.");
      setRecoveryPhase("unverified");
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
          disabled={recoveryPhase !== "ready" || loading || Boolean(sessionId)}
        >
          {loading && !sessionId ? "Đang xử lý…" : "Bắt đầu phiên"}
        </button>
        {recoveryPhase === "unverified" && (
          <button
            type="button"
            onClick={() => void checkActiveSession()}
          >
            Thử khôi phục lại
          </button>
        )}
        {sessionId && (
          <button
            type="button"
            onClick={() => void endSession()}
            disabled={loading}
            className="btn-danger"
          >
            {loading ? "Đang xử lý…" : "Kết thúc phiên"}
          </button>
        )}
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
