"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import type {
  LearnerProgress,
  LearningPreferencesPublic,
  LearnerActivityResponsePublic,
  WatchHistoryItemPublic,
  WatchHistoryResponsePublic,
  HistoryDeletionCreatedPublic,
  Capabilities,
} from "@jplearn/domain";
import { api, parseApiResponse } from "../../lib/api";
import { getToken, subscribeAuth } from "../../lib/auth-storage";

function formatDateInTimezone(date: Date, timeZone: string): string {
  try {
    return new Intl.DateTimeFormat("en-CA", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(date);
  } catch {
    return date.toISOString().slice(0, 10);
  }
}

function formatDisplayDate(dateStr: string, timeZone: string): string {
  try {
    const d = new Date(dateStr);
    return new Intl.DateTimeFormat("vi-VN", {
      timeZone,
      weekday: "short",
      day: "numeric",
      month: "numeric",
    }).format(d);
  } catch {
    return dateStr;
  }
}

export default function ProgressPage() {
  const [progress, setProgress] = useState<LearnerProgress | null>(null);
  const [preferences, setPreferences] = useState<LearningPreferencesPublic | null>(null);
  const [activity, setActivity] = useState<LearnerActivityResponsePublic | null>(null);
  const [watchHistory, setWatchHistory] = useState<WatchHistoryItemPublic[]>([]);
  const [deletionNotice, setDeletionNotice] = useState<string | null>(null);
  const [deletionCutoff, setDeletionCutoff] = useState<string | null>(null);
  const [isDeletingHistory, setIsDeletingHistory] = useState(false);
  const [updatingGoal, setUpdatingGoal] = useState(false);
  const [goalError, setGoalError] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);

  const progressGenRef = useRef(0);

  const loadData = useCallback(async () => {
    const token = getToken();
    const gen = ++progressGenRef.current;

    if (!token) {
      setLoading(false);
      setProgress(null);
      setPreferences(null);
      setActivity(null);
      setWatchHistory([]);
      setDeletionNotice(null);
      setGoalError(null);
      setHistoryError(null);
      return;
    }

    setLoading(true);
    setError("");

    try {
      // 0. Capabilities (non-fatal)
      try {
        const resCap = await api("/capabilities", { token });
        if (resCap.ok && gen === progressGenRef.current) {
          const capData = await parseApiResponse<Capabilities>(resCap);
          setCapabilities(capData);
        }
      } catch {
        // Non-fatal
      }

      // 1. Baseline Progress
      const resProg = await api("/progress", { token });
      if (gen !== progressGenRef.current) return;

      if (resProg.ok) {
        const data = await parseApiResponse<LearnerProgress>(resProg);
        setProgress(data);
      } else {
        setError("Không thể tải thông tin tiến độ.");
      }

      // 2. Learning Preferences (PR5)
      let currentTz = "Asia/Tokyo";
      try {
        const resPref = await api("/me/learning-preferences", { token });
        if (gen === progressGenRef.current && resPref.ok) {
          const prefData = await parseApiResponse<LearningPreferencesPublic>(resPref);
          setPreferences(prefData);
          if (prefData.current_policy?.timezone) {
            currentTz = prefData.current_policy.timezone;
          } else if (prefData.timezone) {
            currentTz = prefData.timezone;
          }
        }
      } catch {
        // Non-fatal
      }

      if (gen !== progressGenRef.current) return;

      // 3. 7-day Activity computed in policy timezone
      try {
        const now = new Date();
        const past = new Date(now.getTime() - 6 * 24 * 60 * 60 * 1000);
        const fromStr = formatDateInTimezone(past, currentTz);
        const toStr = formatDateInTimezone(now, currentTz);

        const resAct = await api(`/me/activity?from=${fromStr}&to=${toStr}`, { token });
        if (gen === progressGenRef.current && resAct.ok) {
          const actData = await parseApiResponse<LearnerActivityResponsePublic>(resAct);
          setActivity(actData);
        }
      } catch {
        // Non-fatal
      }

      if (gen !== progressGenRef.current) return;

      // 4. Watch History (PR5)
      try {
        const resHist = await api("/me/watch-history?limit=5", { token });
        if (gen === progressGenRef.current && resHist.ok) {
          const histData = await parseApiResponse<WatchHistoryResponsePublic>(resHist);
          const rawItems = histData?.items || [];
          // Filter out items hidden by an in-session deletion cutoff
          if (deletionCutoff) {
            const cutoffMs = new Date(deletionCutoff).getTime();
            setWatchHistory(rawItems.filter((it) => new Date(it.created_at).getTime() > cutoffMs));
          } else {
            setWatchHistory(rawItems);
          }
        }
      } catch {
        // Non-fatal
      }
    } catch {
      if (gen === progressGenRef.current) {
        setError("Lỗi kết nối máy chủ khi lấy tiến độ.");
      }
    } finally {
      if (gen === progressGenRef.current) {
        setLoading(false);
      }
    }
  }, [deletionCutoff]);

  const handleUpdateGoal = async (newGoalMinutes: number) => {
    if (!preferences) return;
    setUpdatingGoal(true);
    setGoalError(null);

    const token = getToken();
    if (!token) return;

    try {
      const res = await api("/me/learning-preferences", {
        method: "PUT",
        token,
        body: JSON.stringify({
          expected_revision: preferences.revision,
          daily_goal_minutes: newGoalMinutes,
          preferred_topic_ids: preferences.preferred_topic_ids,
          timezone: preferences.current_policy?.timezone || preferences.timezone,
        }),
      });

      if (res.ok) {
        const updated = await parseApiResponse<LearningPreferencesPublic>(res);
        setPreferences(updated);
        // Refresh activity to reflect new goal
        void loadData();
      } else if (res.status === 409) {
        setGoalError("Mục tiêu đã được cập nhật ở nơi khác (xung đột phiên bản). Vui lòng thử lại sau khi dữ liệu được làm mới.");
        // Fetch fresh preferences revision
        try {
          const freshRes = await api("/me/learning-preferences", { token });
          if (freshRes.ok) {
            const freshPref = await parseApiResponse<LearningPreferencesPublic>(freshRes);
            setPreferences(freshPref);
          }
        } catch {
          // Non-fatal
        }
      } else {
        setGoalError(`Không thể cập nhật mục tiêu (mã phản hồi: ${res.status}).`);
      }
    } catch {
      setGoalError("Lỗi mạng khi cập nhật mục tiêu học.");
    } finally {
      setUpdatingGoal(false);
    }
  };

  const handleDeleteWatchHistory = async () => {
    if (!confirm("Bạn có chắc chắn muốn xóa toàn bộ lịch sử xem?")) return;

    setIsDeletingHistory(true);
    setHistoryError(null);

    const token = getToken();
    if (!token) return;

    try {
      const res = await api("/me/watch-history", {
        method: "DELETE",
        token,
      });

      if (res.status === 202) {
        const data = await parseApiResponse<HistoryDeletionCreatedPublic>(res);
        setDeletionNotice(
          `Đã yêu cầu xóa lịch sử xem (Mã: ${data.deletion_id.slice(0, 8)}…). Lịch sử đã được ẩn ngay lập tức và tác vụ xóa đang xử lý ở nền.`
        );
        setDeletionCutoff(data.cutoff_time);
        setWatchHistory([]);
      } else {
        setHistoryError(`Không thể xóa lịch sử xem (mã phản hồi: ${res.status}).`);
      }
    } catch {
      setHistoryError("Lỗi kết nối máy chủ khi gửi yêu cầu xóa lịch sử.");
    } finally {
      setIsDeletingHistory(false);
    }
  };

  useEffect(() => {
    void loadData();

    const unsubscribe = subscribeAuth(() => {
      progressGenRef.current += 1;
      void loadData();
    });

    const onFocus = () => {
      void loadData();
    };
    window.addEventListener("focus", onFocus);

    return () => {
      unsubscribe();
      window.removeEventListener("focus", onFocus);
    };
  }, [loadData]);

  const activeGoal = preferences?.current_policy?.daily_goal_minutes ?? preferences?.daily_goal_minutes ?? 15;
  const pendingPolicy = preferences?.pending_policy;

  return (
    <section className="progress-container">
      <h1>Tiến độ</h1>
      <p className="progress-intro">Thời gian nhỏ. Thay đổi lớn.</p>
      <p className="muted">Dành thời gian lắng nghe, để tiếng Nhật dần trở nên quen thuộc.</p>

      {loading ? (
        <div style={{ textAlign: "center", padding: "2rem" }}>
          <p>Đang tải tiến độ…</p>
        </div>
      ) : null}

      {!loading && error ? (
        <div className="status-error" role="alert">
          <p>{error}</p>
          <button type="button" onClick={() => void loadData()} style={{ marginTop: "0.5rem" }}>
            Thử lại
          </button>
        </div>
      ) : null}

      {!loading && !error && !progress ? (
        <div className="login-card" style={{ textAlign: "center" }}>
          <p style={{ marginBottom: "1rem" }}>Hãy đăng nhập để xem thông số và cấp độ CI hiện tại.</p>
          <Link href="/login?redirect=/progress" className="btn-cta btn-primary">
            Đăng nhập ngay
          </Link>
        </div>
      ) : null}

      {!loading && progress ? (
        <>
          {/* Main CI Stats Card */}
          <div className="progress-hero-card">
            <span className="card-level-badge" style={{ fontSize: "0.85rem", padding: "4px 14px" }}>
              Cấp độ hiện tại: Cấp {progress.current_ci_level}
            </span>

            <div className="progress-big-number">
              {progress.minutes_comprehensible}
            </div>
            <div className="progress-label">
              Phút CI tích lũy
            </div>

            <p style={{ marginTop: "1rem", color: "var(--text-muted)", fontSize: "0.95rem" }}>
              {progress.minutes_comprehensible} phút · cấp {progress.current_ci_level}
            </p>
          </div>

          {/* Section: Daily Goal Setting */}
          {preferences && (
            <div
              style={{
                background: "var(--card-bg)",
                border: "2px solid var(--charcoal)",
                borderRadius: "var(--radius-md)",
                padding: "1.5rem",
                boxShadow: "var(--shadow-solid)",
                marginBottom: "2rem",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
                <h2 style={{ fontSize: "1.15rem", fontWeight: 800 }}>Mục tiêu học tập hàng ngày</h2>
                <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                  Múi giờ: {preferences.current_policy?.timezone || preferences.timezone}
                </span>
              </div>

              <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", marginBottom: "1rem" }}>
                Mục tiêu hiện tại: <strong>{activeGoal} phút / ngày</strong>
              </p>

              {pendingPolicy && (
                <div
                  style={{
                    background: "rgba(255, 183, 3, 0.15)",
                    border: "1px solid #d4a373",
                    borderRadius: "var(--radius-sm)",
                    padding: "0.75rem 1rem",
                    marginBottom: "1rem",
                    fontSize: "0.85rem",
                  }}
                >
                  <span style={{ fontWeight: 700 }}>Mục tiêu sắp có hiệu lực: </span>
                  {pendingPolicy.daily_goal_minutes} phút / ngày (hiệu lực từ: {new Date(pendingPolicy.effective_at).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })})
                </div>
              )}

              {goalError && (
                <div className="status-error" role="alert" style={{ marginBottom: "1rem", padding: "0.5rem 1rem" }}>
                  <p>{goalError}</p>
                </div>
              )}

              <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
                {[15, 30, 45, 60].map((goalMinutes) => (
                  <button
                    key={goalMinutes}
                    type="button"
                    disabled={updatingGoal}
                    onClick={() => void handleUpdateGoal(goalMinutes)}
                    className={`filter-pill ${activeGoal === goalMinutes ? "active" : ""}`}
                    style={{
                      padding: "0.5rem 1rem",
                      fontSize: "0.85rem",
                      cursor: updatingGoal ? "wait" : "pointer",
                    }}
                  >
                    {goalMinutes} phút / ngày
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Section: 7-day Activity Chart */}
          {activity && (
            <div
              style={{
                background: "var(--card-bg)",
                border: "2px solid var(--charcoal)",
                borderRadius: "var(--radius-md)",
                padding: "1.5rem",
                boxShadow: "var(--shadow-solid)",
                marginBottom: "2rem",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <h2 style={{ fontSize: "1.15rem", fontWeight: 800 }}>Hoạt động 7 ngày gần đây</h2>
                <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                  Chuỗi học: {activity.current_streak_days} ngày liên tiếp
                </span>
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: `repeat(${Math.max(activity.items.length, 1)}, 1fr)`,
                  gap: "0.5rem",
                  alignItems: "end",
                  minHeight: "140px",
                  padding: "1rem 0",
                  borderBottom: "1px solid var(--charcoal)",
                }}
              >
                {activity.items.map((item) => {
                  const watchMins = Math.round(item.active_watch_seconds / 60);
                  const heightPercent = item.goal_seconds > 0
                    ? Math.min(Math.round((item.active_watch_seconds / item.goal_seconds) * 100), 100)
                    : 0;

                  return (
                    <div key={item.date} style={{ textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center", gap: "0.25rem" }}>
                      <span style={{ fontSize: "0.75rem", fontWeight: 700 }}>{watchMins}m</span>
                      <div
                        style={{
                          width: "100%",
                          maxWidth: "32px",
                          height: "80px",
                          background: "var(--color-bg, #f3f4f6)",
                          borderRadius: "var(--radius-sm)",
                          display: "flex",
                          alignItems: "flex-end",
                          overflow: "hidden",
                        }}
                      >
                        <div
                          style={{
                            width: "100%",
                            height: `${Math.max(heightPercent, item.active_watch_seconds > 0 ? 8 : 0)}%`,
                            background: item.goal_met ? "var(--pink)" : "var(--charcoal)",
                            transition: "height 0.3s ease",
                          }}
                        />
                      </div>
                      <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                        {formatDisplayDate(item.date, item.timezone)}
                      </span>
                    </div>
                  );
                })}
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", marginTop: "0.75rem", fontSize: "0.85rem" }}>
                <span>Tổng thời gian nghe chủ động: <strong>{Math.round(activity.total_active_watch_seconds / 60)} phút</strong></span>
                <span>Số ngày đạt mục tiêu: <strong>{activity.days_goal_met}/7</strong></span>
              </div>
            </div>
          )}

          {/* Section: Watch History */}
          <div
            style={{
              background: "var(--card-bg)",
              border: "2px solid var(--charcoal)",
              borderRadius: "var(--radius-md)",
              padding: "1.5rem",
              boxShadow: "var(--shadow-solid)",
              marginBottom: "2rem",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
              <h2 style={{ fontSize: "1.15rem", fontWeight: 800 }}>Lịch sử xem gần đây</h2>
              {watchHistory.length > 0 && (
                <button
                  type="button"
                  disabled={isDeletingHistory}
                  onClick={() => void handleDeleteWatchHistory()}
                  style={{
                    fontSize: "0.8rem",
                    padding: "0.3rem 0.75rem",
                    background: "#fee2e2",
                    color: "#b91c1c",
                    border: "1px solid #b91c1c",
                    borderRadius: "var(--radius-sm)",
                    cursor: isDeletingHistory ? "wait" : "pointer",
                    fontWeight: 700,
                  }}
                >
                  {isDeletingHistory ? "Đang gửi yêu cầu…" : "Xóa lịch sử"}
                </button>
              )}
            </div>

            {deletionNotice && (
              <div
                style={{
                  background: "rgba(16, 185, 129, 0.15)",
                  border: "1px solid #10b981",
                  borderRadius: "var(--radius-sm)",
                  padding: "0.75rem 1rem",
                  marginBottom: "1rem",
                  fontSize: "0.85rem",
                }}
              >
                {deletionNotice}
              </div>
            )}

            {historyError && (
              <div className="status-error" role="alert" style={{ marginBottom: "1rem", padding: "0.5rem 1rem" }}>
                <p>{historyError}</p>
              </div>
            )}

            {watchHistory.length === 0 ? (
              <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
                Chưa có lịch sử xem nào được ghi nhận.
              </p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                {watchHistory.map((item) => (
                  <div
                    key={item.playback_id}
                    data-playback-id={item.playback_id}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      padding: "0.75rem",
                      border: "1px solid var(--charcoal)",
                      borderRadius: "var(--radius-sm)",
                      background: "#ffffff",
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 700, fontSize: "0.95rem" }}>
                        {item.title_jp || item.topic_id}
                      </div>
                      <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                        {item.topic_id} · {item.item_type} · Đã nghe: {Math.round(item.total_active_ms / 1000)}s / {item.duration_seconds}s
                      </div>
                    </div>

                    <Link
                      href={`/session?item_id=${item.catalog_item_id}`}
                      className="btn-cta btn-primary"
                      style={{ fontSize: "0.8rem", padding: "0.3rem 0.8rem" }}
                    >
                      Học lại ↗
                    </Link>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      ) : null}
    </section>
  );
}
