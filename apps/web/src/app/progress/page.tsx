"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import type { LearnerProgress } from "@jplearn/domain";
import { api, parseApiResponse } from "../../lib/api";
import { getToken, subscribeAuth } from "../../lib/auth-storage";

export default function ProgressPage() {
  const [progress, setProgress] = useState<LearnerProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadProgress = useCallback(async () => {
    const token = getToken();
    if (!token) {
      setLoading(false);
      setProgress(null);
      return;
    }

    setLoading(true);
    setError("");
    try {
      const res = await api("/progress", { token });
      if (res.ok) {
        const data = await parseApiResponse<LearnerProgress>(res);
        setProgress(data);
      } else {
        setError("Không thể tải thông tin tiến độ.");
      }
    } catch {
      setError("Lỗi kết nối máy chủ khi lấy tiến độ.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadProgress();

    const unsubscribe = subscribeAuth(() => {
      void loadProgress();
    });

    const onFocus = () => {
      void loadProgress();
    };
    window.addEventListener("focus", onFocus);

    return () => {
      unsubscribe();
      window.removeEventListener("focus", onFocus);
    };
  }, [loadProgress]);

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
        <div className="status-error">
          <p>{error}</p>
          <button type="button" onClick={() => void loadProgress()} style={{ marginTop: "0.5rem" }}>
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
      ) : null}
    </section>
  );
}
