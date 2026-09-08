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

      {!loading && !progress ? (
        <div className="login-card" style={{ textAlign: "center" }}>
          <p style={{ marginBottom: "1rem" }}>Hãy đăng nhập để xem thông số và cấp độ CI hiện tại.</p>
          <Link href="/login?redirect=/progress" className="btn-cta btn-primary">
            Đăng nhập ngay
          </Link>
        </div>
      ) : null}

      {!loading && progress ? (
        <>
          <div className="progress-hero-card">
            <span className="card-level-badge" style={{ fontSize: "0.85rem", padding: "4px 14px" }}>
              Cấp độ hiện tại: Cấp {progress.current_ci_level}
            </span>

            <div className="progress-big-number">
              {progress.minutes_comprehensible}
            </div>
            <div className="progress-label">
              CI Minutes Tích Luỹ
            </div>

            <p style={{ marginTop: "1rem", color: "var(--text-muted)", fontSize: "0.95rem" }}>
              {progress.minutes_comprehensible} phút · cấp {progress.current_ci_level}
            </p>

            <div style={{ marginTop: "2rem", display: "flex", justifyContent: "center", gap: "1rem" }}>
              <Link href="/catalog" className="btn-cta btn-primary">
                Tiếp tục học trong Catalog
              </Link>
              <button type="button" onClick={() => void loadProgress()}>
                Làm mới
              </button>
            </div>
          </div>

          <div className="strength-card">
            <h2 style={{ fontSize: "1.1rem", fontWeight: 800, marginBottom: "0.5rem" }}>
              Nguyên tắc ghi nhận thời gian CI
            </h2>
            <p style={{ color: "var(--text-muted)", fontSize: "0.95rem", lineHeight: 1.7 }}>
              Hệ thống JPLearn chỉ ghi nhận thời gian thực khi bạn bắt đầu và hoàn thành phiên học. Mọi thời lượng được tính toán và làm tròn theo công thức toán học từ máy chủ (không tự động cộng giả lập ở giao diện), đảm bảo tính minh bạch tuyệt đối cho hành trình nạp ngôn ngữ của bạn.
            </p>
          </div>
        </>
      ) : null}
    </section>
  );
}

