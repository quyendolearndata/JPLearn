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
  classifySessionRecoveryBootstrap,
  classifySessionStatusFailure,
  classifySessionStatusResponse,
  createSessionOperationGuard,
  isLearningSessionResponse,
  isSessionOperationCurrent,
} from "../../lib/session-recovery";
import {
  clearSessionRecord,
  inspectSessionRecord,
  newIdempotencyKey,
  prepareStartingSession,
  promoteToActive,
  readSessionRecord,
  recoveryRequestFor,
  writeSessionRecord,
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
  const [activeOperation, setActiveOperation] = useState<"recovery" | "start" | "end" | null>(null);

  const recoveryAttemptRef = useRef(0);
  const operationGuardRef = useRef(createSessionOperationGuard());
  const operationAbortRef = useRef<AbortController | null>(null);

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
    const bootstrap = classifySessionRecoveryBootstrap(getToken(), currentUserId());

    if (bootstrap.kind === "awaiting_identity") {
      setRecoveryPhase("initializing");
      setStatus("Vui lòng đăng nhập để kiểm tra phiên.");
      return;
    }
    const { token, userId } = bootstrap;
    try { localStorage.removeItem("jplearn_active_session"); } catch {}

    const inspection = inspectSessionRecord(userId);
    if (inspection.kind === "unavailable") {
      setStatus("Không thể truy cập dữ liệu phiên trên trình duyệt.");
      setRecoveryPhase("unverified");
      return;
    }
    if (inspection.kind === "empty") {
      setRecoveryPhase("ready");
      setStatus("");
      return;
    }
    const stored = inspection.record;

    const recoveryRequest = recoveryRequestFor(stored);
    if (!recoveryRequest) {
      const cleared = clearSessionRecord(userId);
      setStatus(
        cleared
          ? "Dữ liệu khôi phục phiên không hợp lệ."
          : "Dữ liệu khôi phục phiên không hợp lệ và chưa thể xóa khỏi trình duyệt.",
      );
      setRecoveryPhase(cleared ? "ready" : "unverified");
      return;
    }

    const ticket = operationGuardRef.current.begin("recovery");
    if (!ticket) return;
    const attempt = ++recoveryAttemptRef.current;
    const controller = new AbortController();
    operationAbortRef.current = controller;
    const isCurrentAttempt = () =>
      recoveryAttemptRef.current === attempt
      && isSessionOperationCurrent(operationGuardRef.current, ticket, userId, currentUserId());
    setActiveOperation("recovery");
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
          signal: controller.signal,
        });

        if (!isCurrentAttempt()) return;
        if (!res.ok) {
          const disposition = classifyReplayFailure(res.status);
          if (disposition === "auth") return;
          if (disposition === "terminal") {
            const cleared = clearSessionRecord(userId);
            setSessionId(null);
            setStartedAt(null);
            setClip(null);
            setStatus(
              cleared
                ? "Không thể khôi phục phiên do khóa chống trùng bị xung đột."
                : "Khóa chống trùng bị xung đột và chưa thể xóa dữ liệu phiên.",
            );
            setRecoveryPhase(cleared ? "ready" : "unverified");
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
          const cleared = clearSessionRecord(userId);
          setSessionId(null);
          setStartedAt(null);
          setClip(null);
          setStatus(
            cleared
              ? "Phiên đã kết thúc."
              : "Phiên đã kết thúc nhưng chưa thể xóa dữ liệu phiên trên trình duyệt.",
          );
          setRecoveryPhase(cleared ? "ready" : "unverified");
          return;
        }

        const promotion = promoteToActive(
          stored,
          body.id,
          body.started_at,
          (record) => writeSessionRecord(userId, record),
        );
        setSessionId(promotion.record.sessionId!);
        setStartedAt(new Date(promotion.record.startedAt));
        setElapsedSeconds(Math.max(0, Math.floor((Date.now() - new Date(promotion.record.startedAt).getTime()) / 1000)));
        if (promotion.kind === "unverified") {
          setStatus("Phiên đang chạy nhưng chưa lưu được trạng thái trên trình duyệt.");
          setRecoveryPhase("unverified");
          return;
        }
        await loadClip(recoveryRequest.itemId, isCurrentAttempt);
        if (!isCurrentAttempt()) return;
        setStatus("Phiên đang chạy (đã khôi phục).");
        setRecoveryPhase("ready");
        return;
      }

      // 2. active / ending / outcome_unknown: ask the server what really happened.
      const res = await api(`/sessions/${recoveryRequest.sessionId}`, {
        token,
        signal: controller.signal,
      });
      if (!isCurrentAttempt()) return;
      if (res.status === 401) return;
      if (res.status === 403 || res.status === 404) {
        const cleared = clearSessionRecord(userId);
        setSessionId(null);
        setStartedAt(null);
        setClip(null);
        setStatus(
          cleared
            ? res.status === 403
              ? "Bạn không có quyền khôi phục phiên này."
              : "Phiên cần khôi phục không còn tồn tại."
            : "Phiên không thể khôi phục và chưa thể xóa dữ liệu trên trình duyệt.",
        );
        setRecoveryPhase(cleared ? "ready" : "unverified");
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
        const cleared = clearSessionRecord(userId);
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
        setStatus(
          cleared
            ? "Phiên đã kết thúc."
            : "Phiên đã kết thúc nhưng chưa thể xóa dữ liệu phiên trên trình duyệt.",
        );
        setRecoveryPhase(cleared ? "ready" : "unverified");
        return;
      }

      // Still active on the server.
      const promotion = promoteToActive(
        stored,
        recoveryRequest.sessionId,
        data.started_at,
        (record) => writeSessionRecord(userId, record),
      );
      const start = new Date(promotion.record.startedAt);
      setSessionId(promotion.record.sessionId!);
      setStartedAt(start);
      setElapsedSeconds(Math.max(0, Math.floor((Date.now() - start.getTime()) / 1000)));
      if (promotion.kind === "unverified") {
        setStatus("Phiên đang chạy nhưng chưa lưu được trạng thái trên trình duyệt.");
        setRecoveryPhase("unverified");
        return;
      }
      await loadClip(recoveryRequest.itemId, isCurrentAttempt);
      if (!isCurrentAttempt()) return;
      setStatus(stored.state === "active" ? "Phiên đang chạy." : "Phiên vẫn đang chạy trên máy chủ — hãy kết thúc lại.");
      setRecoveryPhase("ready");
    } catch {
      if (!isCurrentAttempt()) return;
      setStatus("Chưa xác nhận được trạng thái phiên với máy chủ.");
      setRecoveryPhase("unverified");
    } finally {
      if (operationGuardRef.current.finish(ticket)) {
        setActiveOperation(null);
        if (operationAbortRef.current === controller) operationAbortRef.current = null;
      }
    }
  }, [loadClip]);

  useEffect(() => {
    void checkActiveSession();
    return () => {
      recoveryAttemptRef.current += 1;
      operationGuardRef.current.cancel();
      operationAbortRef.current?.abort();
      operationAbortRef.current = null;
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

    const startedAtIso = new Date().toISOString();
    const preparation = prepareStartingSession(
      inspectSessionRecord(userId),
      {
        startedAt: startedAtIso,
        itemId: requestedItemId || undefined,
      },
      newIdempotencyKey,
    );
    if (preparation.kind === "unavailable") {
      setRecoveryPhase("unverified");
      setStatus("Không thể truy cập dữ liệu phiên trên trình duyệt.");
      return;
    }
    if (preparation.kind === "existing") {
      setRecoveryPhase("unverified");
      setStatus("Cần khôi phục phiên đã lưu trước khi bắt đầu phiên mới.");
      return;
    }

    // Persist "starting" state BEFORE sending POST /sessions
    const startingRecord = preparation.record;
    if (!writeSessionRecord(userId, startingRecord)) {
      setRecoveryPhase("unverified");
      setStatus("Không thể lưu dữ liệu phiên trên trình duyệt.");
      return;
    }

    const ticket = operationGuardRef.current.begin("start");
    if (!ticket) {
      setRecoveryPhase("unverified");
      setStatus("Phiên đã lưu cần được khôi phục trước khi tiếp tục.");
      return;
    }
    const controller = new AbortController();
    operationAbortRef.current = controller;
    const isCurrentOperation = () =>
      isSessionOperationCurrent(operationGuardRef.current, ticket, userId, currentUserId());
    setActiveOperation("start");
    setLoading(true);
    setCompletedSummary(null);
    const idempotencyKey = startingRecord.idempotencyKey;

    try {
      const res = await api("/sessions", {
        method: "POST",
        token,
        headers: {
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify({ device_class: "web" }),
        signal: controller.signal,
      });

      if (!isCurrentOperation()) return;
      if (!res.ok) {
        const disposition = classifyReplayFailure(res.status);
        if (disposition === "auth") return;
        if (disposition === "terminal") {
          const cleared = clearSessionRecord(userId);
          setStatus(
            cleared
              ? "Không thể bắt đầu phiên do khóa chống trùng bị xung đột."
              : "Khóa chống trùng bị xung đột và chưa thể xóa dữ liệu phiên.",
          );
          setRecoveryPhase(cleared ? "ready" : "unverified");
          return;
        }
        const err = await parseApiError(res);
        if (!isCurrentOperation()) return;
        setStatus(err.message || "Không thể bắt đầu phiên.");
        setRecoveryPhase("unverified");
        return;
      }

      const body = await parseApiResponse<unknown>(res);
      if (!isCurrentOperation()) return;
      if (!isLearningSessionResponse(body)) {
        setStatus("Dữ liệu phiên không hợp lệ.");
        setRecoveryPhase("unverified");
        return;
      }

      // IMMEDIATELY update sessionStorage to "active" BEFORE fetching catalog
      const promotion = promoteToActive(
        startingRecord,
        body.id,
        body.started_at,
        (record) => writeSessionRecord(userId, record),
      );
      const start = new Date(promotion.record.startedAt);
      setSessionId(promotion.record.sessionId!);
      setStartedAt(start);
      setElapsedSeconds(0);
      if (promotion.kind === "unverified") {
        setStatus("Phiên đang chạy nhưng chưa lưu được trạng thái trên trình duyệt.");
        setRecoveryPhase("unverified");
        return;
      }

      await loadClip(requestedItemId, isCurrentOperation);
    } catch {
      if (!isCurrentOperation()) return;
      // Keep "starting" in storage so reload can recover using same idempotency key
      setStatus("Lỗi kết nối máy chủ khi bắt đầu phiên.");
      setRecoveryPhase("unverified");
    } finally {
      if (operationGuardRef.current.finish(ticket)) {
        setLoading(false);
        setActiveOperation(null);
        if (operationAbortRef.current === controller) operationAbortRef.current = null;
      }
    }
  };

  // End learning session
  const endSession = async () => {
    const token = getToken();
    const userId = currentUserId();
    const targetSessionId = sessionId;
    if (!token || !targetSessionId || !userId) return;

    const ticket = operationGuardRef.current.begin("end");
    if (!ticket) return;
    const controller = new AbortController();
    operationAbortRef.current = controller;
    const isCurrentOperation = () =>
      isSessionOperationCurrent(operationGuardRef.current, ticket, userId, currentUserId());
    setActiveOperation("end");
    setLoading(true);

    const rec = readSessionRecord(userId);
    if (rec) writeSessionRecord(userId, { ...rec, state: "ending", sessionId: targetSessionId });

    const handleStatusFailure = (statusCode: number) => {
      const disposition = classifySessionStatusFailure(statusCode);
      if (disposition === "auth") return;
      if (disposition === "terminal") {
        const cleared = clearSessionRecord(userId);
        setSessionId(null);
        setStartedAt(null);
        setClip(null);
        setStatus(
          cleared
            ? statusCode === 403
              ? "Bạn không có quyền kiểm tra phiên này."
              : "Phiên cần kiểm tra không còn tồn tại."
            : "Phiên không thể kiểm tra và chưa thể xóa dữ liệu trên trình duyệt.",
        );
        setRecoveryPhase(cleared ? "ready" : "unverified");
        return;
      }
      setStatus("Chưa xác nhận được trạng thái phiên với máy chủ.");
      setRecoveryPhase("unverified");
    };

    try {
      const res = await api(`/sessions/${targetSessionId}/end`, {
        method: "POST",
        token,
        signal: controller.signal,
      });

      if (!isCurrentOperation()) return;
      if (!res.ok) {
        const latest = readSessionRecord(userId);
        if (latest) {
          writeSessionRecord(userId, {
            ...latest,
            state: "outcome_unknown",
            sessionId: targetSessionId,
          });
        }

        const checkRes = await api(`/sessions/${targetSessionId}`, {
          token,
          signal: controller.signal,
        });
        if (!isCurrentOperation()) return;
        if (!checkRes.ok) {
          handleStatusFailure(checkRes.status);
          return;
        }
        const checkBody = await parseApiResponse<unknown>(checkRes);
        if (!isCurrentOperation()) return;
        const checked = classifySessionStatusResponse(checkBody, targetSessionId);
        if (checked.kind === "invalid") {
          setStatus("Dữ liệu trạng thái phiên không hợp lệ.");
          setRecoveryPhase("unverified");
          return;
        }
        if (checked.kind === "ended") {
          const cleared = clearSessionRecord(userId);
          const progressRes = await api("/progress", {
            token,
            signal: controller.signal,
          });
          if (!isCurrentOperation()) return;
          const progress = progressRes.ok
            ? await parseApiResponse<{
                minutes_comprehensible: number;
                current_ci_level: number;
              }>(progressRes)
            : null;
          if (!isCurrentOperation()) return;
          setCompletedSummary({
            minutesComprehensible: progress?.minutes_comprehensible ?? 0,
            currentCiLevel: progress?.current_ci_level ?? 0,
            durationSeconds: checked.session.duration_seconds ?? elapsedSeconds,
          });
          setSessionId(null);
          setClip(null);
          setStatus(
            cleared
              ? "Đã kết thúc phiên."
              : "Đã kết thúc phiên nhưng chưa thể xóa dữ liệu phiên trên trình duyệt.",
          );
          setRecoveryPhase(cleared ? "ready" : "unverified");
          return;
        }
        const err = await parseApiError(res);
        if (!isCurrentOperation()) return;
        setStatus(err.message || "Không thể kết thúc phiên. Vui lòng thử lại.");
        return;
      }

      const progress = await parseApiResponse<{
        minutes_comprehensible: number;
        current_ci_level: number;
      }>(res);
      if (!isCurrentOperation()) return;

      const cleared = clearSessionRecord(userId);
      setCompletedSummary({
        minutesComprehensible: progress?.minutes_comprehensible ?? 0,
        currentCiLevel: progress?.current_ci_level ?? 0,
        durationSeconds: elapsedSeconds,
      });
      setSessionId(null);
      setClip(null);
      setStatus(
        cleared
          ? "Đã kết thúc phiên."
          : "Đã kết thúc phiên nhưng chưa thể xóa dữ liệu phiên trên trình duyệt.",
      );
      setRecoveryPhase(cleared ? "ready" : "unverified");
    } catch {
      if (!isCurrentOperation()) return;
      const latest = readSessionRecord(userId);
      if (latest) {
        writeSessionRecord(userId, {
          ...latest,
          state: "outcome_unknown",
          sessionId: targetSessionId,
        });
      }
      try {
        const checkRes = await api(`/sessions/${targetSessionId}`, {
          token,
          signal: controller.signal,
        });
        if (!isCurrentOperation()) return;
        if (!checkRes.ok) {
          handleStatusFailure(checkRes.status);
          return;
        }
        const checkBody = await parseApiResponse<unknown>(checkRes);
        if (!isCurrentOperation()) return;
        const checked = classifySessionStatusResponse(checkBody, targetSessionId);
        if (checked.kind === "invalid") {
          setStatus("Dữ liệu trạng thái phiên không hợp lệ.");
          setRecoveryPhase("unverified");
          return;
        }
        if (checked.kind === "ended") {
          const cleared = clearSessionRecord(userId);
          setSessionId(null);
          setClip(null);
          setStatus(
            cleared
              ? "Đã kết thúc phiên."
              : "Đã kết thúc phiên nhưng chưa thể xóa dữ liệu phiên trên trình duyệt.",
          );
          setRecoveryPhase(cleared ? "ready" : "unverified");
          return;
        }
      } catch {
        if (!isCurrentOperation()) return;
      }
      if (!isCurrentOperation()) return;
      setStatus("Lỗi kết nối khi kết thúc phiên.");
      setRecoveryPhase("unverified");
    } finally {
      if (operationGuardRef.current.finish(ticket)) {
        setLoading(false);
        setActiveOperation(null);
        if (operationAbortRef.current === controller) operationAbortRef.current = null;
      }
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
          disabled={recoveryPhase !== "ready" || loading || activeOperation !== null || Boolean(sessionId)}
        >
          {loading && !sessionId ? "Đang xử lý…" : "Bắt đầu phiên"}
        </button>
        {recoveryPhase === "unverified" && (
          <button
            type="button"
            onClick={() => void checkActiveSession()}
            disabled={loading || activeOperation !== null}
          >
            Thử khôi phục lại
          </button>
        )}
        {sessionId && (
          <button
            type="button"
            onClick={() => void endSession()}
            disabled={loading || activeOperation !== null}
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
