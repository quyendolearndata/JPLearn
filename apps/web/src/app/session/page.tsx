"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import type { CatalogItemPublic } from "@jplearn/domain";
import { api, parseApiError, parseApiResponse } from "../../lib/api";
import { getToken, getUser } from "../../lib/auth-storage";
import { CiPlayer } from "../../components/ci-player";
import {
  completeAutomaticCatalogRefetch,
  createMediaRecoveryCycle,
  reconcileMediaRecoveryTarget,
  requestAutomaticCatalogRefetch,
  restartMediaRecoveryManually,
  selectSessionCatalogItem,
} from "../../lib/media-recovery";
import {
  classifyEndedProgress,
  classifyReplayFailure,
  classifySessionRecoveryBootstrap,
  classifySessionStatusFailure,
  classifySessionStatusResponse,
  createSessionOperationGuard,
  isLearningSessionResponse,
  isSessionOperationCurrent,
  type EndSummary,
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

type RecoveryPhase = "initializing" | "verifying" | "ready" | "unverified";
type ClipLoadMode = "initial" | "automatic" | "manual";
type ClipLoadResult = "selected" | "unavailable" | "empty" | "failed" | "stale";
type MediaRecoveryState = "idle" | "retrying" | "failed" | "unavailable";

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
  const [summaryUnavailable, setSummaryUnavailable] = useState(false);
  const [recoveryPhase, setRecoveryPhase] = useState<RecoveryPhase>("initializing");
  const [activeOperation, setActiveOperation] = useState<"recovery" | "start" | "end" | null>(null);
  const [mediaRecoveryState, setMediaRecoveryState] = useState<MediaRecoveryState>("idle");

  const recoveryAttemptRef = useRef(0);
  const operationGuardRef = useRef(createSessionOperationGuard());
  const operationAbortRef = useRef<AbortController | null>(null);
  const clipAbortRef = useRef<AbortController | null>(null);
  const clipRequestRef = useRef(0);
  const sessionIdRef = useRef<string | null>(null);
  const clipRef = useRef<CatalogItemPublic | null>(null);
  const activeOperationRef = useRef<"recovery" | "start" | "end" | null>(null);
  const targetItemIdRef = useRef<string | null>(requestedItemId);
  const mediaRecoveryCycleRef = useRef(createMediaRecoveryCycle(requestedItemId));
  const mediaManualRetryRef = useRef(false);
  const mountedRef = useRef(true);

  const applySessionId = useCallback((value: string | null) => {
    sessionIdRef.current = value;
    setSessionId(value);
  }, []);

  const applyClip = useCallback((value: CatalogItemPublic | null) => {
    clipRef.current = value;
    setClip(value);
  }, []);

  const applyActiveOperation = useCallback((value: "recovery" | "start" | "end" | null) => {
    activeOperationRef.current = value;
    setActiveOperation(value);
  }, []);

  const loadClip = useCallback(async (
    targetItemId?: string | null,
    shouldApply: () => boolean = () => true,
    mode: ClipLoadMode = "initial",
  ): Promise<ClipLoadResult> => {
    const token = getToken();
    if (!token) return "failed";
    const normalizedTarget = targetItemId || null;
    const previousClip = clipRef.current;
    targetItemIdRef.current = normalizedTarget;
    mediaRecoveryCycleRef.current = reconcileMediaRecoveryTarget(
      mediaRecoveryCycleRef.current,
      normalizedTarget,
    );
    const requestId = ++clipRequestRef.current;
    clipAbortRef.current?.abort();
    const controller = new AbortController();
    clipAbortRef.current = controller;
    if (mode !== "initial") setMediaRecoveryState("retrying");

    let items: CatalogItemPublic[];
    try {
      const catRes = await api("/catalog", { token, signal: controller.signal });
      if (!catRes.ok) throw new Error("catalog request failed");
      const catalog = await parseApiResponse<{ items: CatalogItemPublic[] }>(catRes);
      items = catalog?.items || [];
    } catch {
      if (
        !mountedRef.current
        || requestId !== clipRequestRef.current
        || !shouldApply()
      ) return "stale";
      applyClip(null);
      if (mode === "initial") {
        setMediaRecoveryState("failed");
        setStatus("Phiên đang chạy. Chưa tải được nguồn video.");
      } else {
        setMediaRecoveryState("failed");
        setStatus("Không thể phát nội dung này.");
      }
      return "failed";
    } finally {
      if (clipAbortRef.current === controller) clipAbortRef.current = null;
    }
    if (
      !mountedRef.current
      || requestId !== clipRequestRef.current
      || !shouldApply()
    ) return "stale";

    const selection = selectSessionCatalogItem(items, normalizedTarget);
    if (selection.kind === "unavailable") {
      applyClip(null);
      setMediaRecoveryState("unavailable");
      setStatus("Nội dung này không còn khả dụng.");
      return "unavailable";
    }
    if (selection.kind === "empty") {
      applyClip(null);
      setMediaRecoveryState("idle");
      setStatus("Phiên đang chạy. Chưa có clip published.");
      return "empty";
    }
    if (
      mode === "automatic"
      && previousClip?.id === selection.item.id
      && previousClip.hls_url === selection.item.hls_url
      && previousClip.playback_url === selection.item.playback_url
    ) {
      applyClip(null);
      setMediaRecoveryState("failed");
      setStatus("Không thể phát nội dung này.");
      return "failed";
    }

    targetItemIdRef.current = selection.item.id;
    mediaRecoveryCycleRef.current = reconcileMediaRecoveryTarget(
      mediaRecoveryCycleRef.current,
      selection.item.id,
    );
    let defaultPersisted = true;
    if (selection.choseDefault) {
      const userId = currentUserId();
      const latest = userId ? readSessionRecord(userId) : null;
      if (userId && latest && !latest.itemId && latest.sessionId === sessionIdRef.current) {
        defaultPersisted = writeSessionRecord(userId, {
          ...latest,
          itemId: selection.item.id,
        });
      }
    }
    applyClip(selection.item);
    setMediaRecoveryState("idle");
    if (defaultPersisted) {
      setStatus("Phiên đang chạy.");
    } else {
      setStatus("Phiên đang chạy nhưng chưa lưu được nội dung đã chọn.");
      setRecoveryPhase("unverified");
    }
    return "selected";
  }, [applyClip]);

  const handleEndedSession = useCallback(async (input: {
    token: string;
    userId: string;
    sessionId: string;
    durationSeconds?: number | null;
    fallbackDurationSeconds: number;
    progressResult?: { responseOk: boolean; body: unknown };
    signal: AbortSignal;
    isCurrent: () => boolean;
  }) => {
    if (!input.isCurrent()) return;
    const latest = readSessionRecord(input.userId);
    if (latest) {
      writeSessionRecord(input.userId, {
        ...latest,
        state: "outcome_unknown",
        sessionId: input.sessionId,
      });
    }
    clipRequestRef.current += 1;
    clipAbortRef.current?.abort();
    clipAbortRef.current = null;
    applySessionId(null);
    setStartedAt(null);
    setElapsedSeconds(0);
    applyClip(null);
    targetItemIdRef.current = null;
    mediaRecoveryCycleRef.current = createMediaRecoveryCycle(null);
    setMediaRecoveryState("idle");
    setCompletedSummary(null);
    setSummaryUnavailable(false);
    setRecoveryPhase("verifying");
    setStatus("Đang tải tổng kết...");

    let progressResult = input.progressResult;
    if (!progressResult) {
      try {
        const progressResponse = await api("/progress", {
          token: input.token,
          signal: input.signal,
        });
        if (!input.isCurrent()) return;
        progressResult = {
          responseOk: progressResponse.ok,
          body: progressResponse.ok
            ? await parseApiResponse<unknown>(progressResponse)
            : null,
        };
      } catch {
        progressResult = { responseOk: false, body: null };
      }
    }
    if (!input.isCurrent()) return;

    const transition = classifyEndedProgress({
      responseOk: progressResult.responseOk,
      body: progressResult.body,
      durationSeconds: input.durationSeconds,
      fallbackDurationSeconds: input.fallbackDurationSeconds,
    });
    if (transition.kind === "unavailable") {
      setStatus("Phiên đã kết thúc; chưa tải được tổng kết");
      setSummaryUnavailable(true);
      setRecoveryPhase("unverified");
      return;
    }

    const cleared = clearSessionRecord(input.userId);
    setCompletedSummary(transition.summary);
    setStatus(
      cleared
        ? "Đã kết thúc phiên."
        : "Đã kết thúc phiên nhưng chưa thể xóa dữ liệu phiên trên trình duyệt.",
    );
    setRecoveryPhase(cleared ? "ready" : "unverified");
  }, [applyClip, applySessionId]);

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
    applyActiveOperation("recovery");
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
            applySessionId(null);
            setStartedAt(null);
            applyClip(null);
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
          await handleEndedSession({
            token,
            userId,
            sessionId: body.id,
            durationSeconds: body.duration_seconds,
            fallbackDurationSeconds: Math.max(
              0,
              Math.floor((Date.parse(body.ended_at) - Date.parse(body.started_at)) / 1000),
            ),
            signal: controller.signal,
            isCurrent: isCurrentAttempt,
          });
          return;
        }

        const promotion = promoteToActive(
          stored,
          body.id,
          body.started_at,
          (record) => writeSessionRecord(userId, record),
        );
        applySessionId(promotion.record.sessionId!);
        setStartedAt(new Date(promotion.record.startedAt));
        setElapsedSeconds(Math.max(0, Math.floor((Date.now() - new Date(promotion.record.startedAt).getTime()) / 1000)));
        if (promotion.kind === "unverified") {
          setStatus("Phiên đang chạy nhưng chưa lưu được trạng thái trên trình duyệt.");
          setRecoveryPhase("unverified");
          return;
        }
        const clipResult = await loadClip(recoveryRequest.itemId, isCurrentAttempt);
        if (!isCurrentAttempt()) return;
        if (clipResult === "stale") return;
        if (clipResult === "selected") setStatus("Phiên đang chạy (đã khôi phục).");
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
        applySessionId(null);
        setStartedAt(null);
        applyClip(null);
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
        await handleEndedSession({
          token,
          userId,
          sessionId: data.id,
          durationSeconds: data.duration_seconds,
          fallbackDurationSeconds: Math.max(
            0,
            Math.floor((Date.parse(data.ended_at) - Date.parse(data.started_at)) / 1000),
          ),
          signal: controller.signal,
          isCurrent: isCurrentAttempt,
        });
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
      applySessionId(promotion.record.sessionId!);
      setStartedAt(start);
      setElapsedSeconds(Math.max(0, Math.floor((Date.now() - start.getTime()) / 1000)));
      if (promotion.kind === "unverified") {
        setStatus("Phiên đang chạy nhưng chưa lưu được trạng thái trên trình duyệt.");
        setRecoveryPhase("unverified");
        return;
      }
      const clipResult = await loadClip(recoveryRequest.itemId, isCurrentAttempt);
      if (!isCurrentAttempt()) return;
      if (clipResult === "stale") return;
      if (clipResult === "selected") {
        setStatus(stored.state === "active" ? "Phiên đang chạy." : "Phiên vẫn đang chạy trên máy chủ — hãy kết thúc lại.");
      }
      setRecoveryPhase("ready");
    } catch {
      if (!isCurrentAttempt()) return;
      setStatus("Chưa xác nhận được trạng thái phiên với máy chủ.");
      setRecoveryPhase("unverified");
    } finally {
      if (operationGuardRef.current.finish(ticket)) {
        applyActiveOperation(null);
        if (operationAbortRef.current === controller) operationAbortRef.current = null;
      }
    }
  }, [applyActiveOperation, applyClip, applySessionId, handleEndedSession, loadClip]);

  useEffect(() => {
    mountedRef.current = true;
    void checkActiveSession();
    return () => {
      mountedRef.current = false;
      recoveryAttemptRef.current += 1;
      operationGuardRef.current.cancel();
      operationAbortRef.current?.abort();
      operationAbortRef.current = null;
      clipRequestRef.current += 1;
      clipAbortRef.current?.abort();
      clipAbortRef.current = null;
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
    targetItemIdRef.current = requestedItemId;
    mediaRecoveryCycleRef.current = createMediaRecoveryCycle(requestedItemId);
    setMediaRecoveryState("idle");

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
    applyActiveOperation("start");
    setLoading(true);
    setCompletedSummary(null);
    setSummaryUnavailable(false);
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
      applySessionId(promotion.record.sessionId!);
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
        applyActiveOperation(null);
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

    clipRequestRef.current += 1;
    clipAbortRef.current?.abort();
    clipAbortRef.current = null;
    const ticket = operationGuardRef.current.begin("end");
    if (!ticket) return;
    const controller = new AbortController();
    operationAbortRef.current = controller;
    const isCurrentOperation = () =>
      isSessionOperationCurrent(operationGuardRef.current, ticket, userId, currentUserId());
    applyActiveOperation("end");
    setLoading(true);

    const rec = readSessionRecord(userId);
    if (rec) writeSessionRecord(userId, { ...rec, state: "ending", sessionId: targetSessionId });

    const handleStatusFailure = (statusCode: number) => {
      const disposition = classifySessionStatusFailure(statusCode);
      if (disposition === "auth") return;
      if (disposition === "terminal") {
        const cleared = clearSessionRecord(userId);
        applySessionId(null);
        setStartedAt(null);
        applyClip(null);
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
          await handleEndedSession({
            token,
            userId,
            sessionId: checked.session.id,
            durationSeconds: checked.session.duration_seconds,
            fallbackDurationSeconds: Math.max(
              0,
              Math.floor(
                (Date.parse(checked.session.ended_at!) - Date.parse(checked.session.started_at)) / 1000,
              ),
            ),
            signal: controller.signal,
            isCurrent: isCurrentOperation,
          });
          return;
        }
        const err = await parseApiError(res);
        if (!isCurrentOperation()) return;
        setStatus(err.message || "Không thể kết thúc phiên. Vui lòng thử lại.");
        return;
      }

      const progress = await parseApiResponse<unknown>(res);
      if (!isCurrentOperation()) return;

      await handleEndedSession({
        token,
        userId,
        sessionId: targetSessionId,
        durationSeconds: null,
        fallbackDurationSeconds: elapsedSeconds,
        progressResult: { responseOk: true, body: progress },
        signal: controller.signal,
        isCurrent: isCurrentOperation,
      });
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
          await handleEndedSession({
            token,
            userId,
            sessionId: checked.session.id,
            durationSeconds: checked.session.duration_seconds,
            fallbackDurationSeconds: Math.max(
              0,
              Math.floor(
                (Date.parse(checked.session.ended_at!) - Date.parse(checked.session.started_at)) / 1000,
              ),
            ),
            signal: controller.signal,
            isCurrent: isCurrentOperation,
          });
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
        applyActiveOperation(null);
        if (operationAbortRef.current === controller) operationAbortRef.current = null;
      }
    }
  };

  const handleSourceFailure = useCallback(() => {
    const currentSessionId = sessionIdRef.current;
    const targetItemId = targetItemIdRef.current ?? clipRef.current?.id ?? null;
    if (
      !mountedRef.current
      || !currentSessionId
      || !targetItemId
      || activeOperationRef.current !== null
    ) return;

    const decision = requestAutomaticCatalogRefetch(mediaRecoveryCycleRef.current);
    mediaRecoveryCycleRef.current = decision.cycle;
    if (decision.action === "coalesced") return;
    if (decision.action === "exhausted") {
      applyClip(null);
      setMediaRecoveryState("failed");
      setStatus("Không thể phát nội dung này.");
      return;
    }

    const generation = decision.cycle.generation;
    void (async () => {
      await loadClip(
        targetItemId,
        () => (
          mountedRef.current
          && sessionIdRef.current === currentSessionId
          && targetItemIdRef.current === targetItemId
          && mediaRecoveryCycleRef.current.generation === generation
          && activeOperationRef.current === null
        ),
        "automatic",
      );
      if (mediaRecoveryCycleRef.current.generation === generation) {
        mediaRecoveryCycleRef.current = completeAutomaticCatalogRefetch(
          mediaRecoveryCycleRef.current,
        );
      }
    })();
  }, [applyClip, loadClip]);

  const retryMediaSource = useCallback(() => {
    const currentSessionId = sessionIdRef.current;
    const targetItemId = targetItemIdRef.current;
    if (
      mediaManualRetryRef.current
      || !mountedRef.current
      || !currentSessionId
      || activeOperationRef.current !== null
    ) return;

    mediaManualRetryRef.current = true;
    mediaRecoveryCycleRef.current = restartMediaRecoveryManually(
      mediaRecoveryCycleRef.current,
    );
    const generation = mediaRecoveryCycleRef.current.generation;
    setMediaRecoveryState("retrying");
    void (async () => {
      try {
        await loadClip(
          targetItemId,
          () => (
            mountedRef.current
            && sessionIdRef.current === currentSessionId
            && targetItemIdRef.current === targetItemId
            && mediaRecoveryCycleRef.current.generation === generation
            && activeOperationRef.current === null
          ),
          "manual",
        );
      } finally {
        if (mediaRecoveryCycleRef.current.generation === generation) {
          mediaManualRetryRef.current = false;
        }
      }
    })();
  }, [loadClip]);

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

      <p
        className="status-text"
        role={recoveryPhase === "unverified" ? "alert" : undefined}
        style={{ marginTop: "0.5rem", fontWeight: 700, color: sessionId ? "#15803d" : "var(--charcoal)" }}
      >
        {status}
      </p>

      {clip ? (
        <div style={{ marginTop: "1.5rem", marginBottom: "1.5rem" }}>
          <div style={{ borderRadius: "var(--radius-md)", overflow: "hidden", border: "2px solid var(--charcoal)", background: "#000000" }}>
            <CiPlayer
              hlsUrl={clip.hls_url}
              playbackUrl={clip.playback_url}
              onSourceFailure={handleSourceFailure}
            />
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
            {summaryUnavailable ? "Thử tải lại tổng kết" : "Thử khôi phục lại"}
          </button>
        )}
        {sessionId && (mediaRecoveryState === "failed" || mediaRecoveryState === "unavailable") && (
          <button
            type="button"
            onClick={retryMediaSource}
            disabled={loading || activeOperation !== null || mediaManualRetryRef.current}
          >
            Thử tải lại video
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
