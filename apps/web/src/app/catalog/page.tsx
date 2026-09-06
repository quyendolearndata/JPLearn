"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import type { CatalogItemPublic } from "@jplearn/domain";
import { api, parseApiResponse } from "../../lib/api";
import { getToken } from "../../lib/auth-storage";

const TOPIC_LABELS: Record<string, string> = {
  daily_home: "Đời sống hàng ngày",
  food: "Ẩm thực & Ăn uống",
  body: "Cơ thể & Chăm sóc",
  go_somewhere: "Đi lại & Giao thông",
  nature: "Thiên nhiên & Môi trường",
  people: "Con người & Giao tiếp",
};

const VISUAL_SUPPORT_LABELS: Record<string, string> = {
  high: "Trực quan cao",
  medium: "Trực quan trung bình",
  low: "Trực quan thấp",
};

export default function CatalogPage() {
  const [items, setItems] = useState<CatalogItemPublic[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [selectedLevel, setSelectedLevel] = useState<number | null>(null);

  const fetchCatalog = useCallback(async (level: number | null) => {
    setLoading(true);
    setErrorMessage("");

    const token = getToken();
    if (!token) {
      setLoading(false);
      setErrorMessage("Hãy đăng nhập.");
      return;
    }

    try {
      const path = level !== null ? `/catalog?ci_level=${level}` : "/catalog";
      const res = await api(path, { token });

      if (!res.ok) {
        setErrorMessage("Không thể tải danh mục bài học.");
        setItems([]);
        return;
      }

      const body = await parseApiResponse<{ items: CatalogItemPublic[] }>(res);
      setItems(body?.items ?? []);
    } catch {
      setErrorMessage("Lỗi kết nối máy chủ khi tải danh mục.");
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchCatalog(selectedLevel);
  }, [selectedLevel, fetchCatalog]);

  return (
    <section>
      <div className="catalog-header-bar">
        <div>
          <h1>Catalog</h1>
          <p style={{ color: "var(--text-muted)", fontSize: "0.95rem" }}>
            Khám phá các video tiếng Nhật Comprehensible Input được phân cấp chuẩn khoa học.
          </p>
        </div>

        <div className="filter-pills" role="group" aria-label="Lọc theo cấp độ CI">
          <button
            type="button"
            className={`filter-pill ${selectedLevel === null ? "active" : ""}`}
            onClick={() => setSelectedLevel(null)}
          >
            Tất cả cấp độ
          </button>
          {[0, 1, 2, 3, 4].map((level) => (
            <button
              key={level}
              type="button"
              className={`filter-pill ${selectedLevel === level ? "active" : ""}`}
              onClick={() => setSelectedLevel(level)}
            >
              Cấp {level}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div style={{ padding: "3rem 0", textAlign: "center", fontWeight: 700 }}>
          <p>Đang tải danh mục…</p>
        </div>
      ) : null}

      {!loading && errorMessage ? (
        <div className="status-error">
          <p>{errorMessage}</p>
          {errorMessage === "Hãy đăng nhập." ? (
            <div style={{ marginTop: "0.75rem" }}>
              <Link href="/login" className="btn-cta btn-primary" style={{ fontSize: "0.85rem", padding: "0.4rem 1rem" }}>
                Đăng nhập ngay
              </Link>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => void fetchCatalog(selectedLevel)}
              style={{ marginTop: "0.75rem", fontSize: "0.85rem", padding: "0.4rem 1rem" }}
            >
              Thử lại
            </button>
          )}
        </div>
      ) : null}

      {!loading && !errorMessage && items.length === 0 ? (
        <div style={{ padding: "3rem 1rem", textAlign: "center", background: "#ffffff", border: "2px solid var(--charcoal)", borderRadius: "var(--radius-md)", boxShadow: "var(--shadow-solid)" }}>
          <h3>Chưa có nội dung published</h3>
          <p style={{ color: "var(--text-muted)", marginTop: "0.5rem" }}>
            {selectedLevel !== null
              ? `Hiện chưa có bài học nào ở Cấp ${selectedLevel}. Vui lòng chọn cấp độ khác.`
              : "Hiện tại chưa có clip nào trong danh mục."}
          </p>
        </div>
      ) : null}

      <h2 className="sr-only">Danh sách bài học CI</h2>

      {!loading && items.length > 0 ? (
        <div className="catalog-grid">
          {items.map((item) => {
            const topicLabel = TOPIC_LABELS[item.topic_id] ?? item.topic_id;
            const visualLabel = VISUAL_SUPPORT_LABELS[item.visual_support] ?? item.visual_support;

            return (
              <article key={item.id} className="catalog-card">
                <div>
                  <div className="card-top">
                    <span className="card-level-badge">Cấp {item.ci_level}</span>
                    <span style={{ fontSize: "0.8rem", fontWeight: 800, color: "var(--pink)" }}>
                      {item.media_type.toUpperCase()}
                    </span>
                  </div>

                  <h3>{topicLabel}</h3>

                  <div className="card-meta">
                    <span title="Thông số kỹ thuật">
                      {item.topic_id} · {item.media_type} · {item.duration_seconds}s
                    </span>
                    <span>{visualLabel}</span>
                  </div>
                </div>

                <div style={{ marginTop: "1rem" }}>
                  <Link
                    href={`/session?item_id=${item.id}`}
                    className="btn-cta btn-primary"
                    style={{ width: "100%", boxSizing: "border-box" }}
                  >
                    Vào học bài này
                  </Link>
                </div>
              </article>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}
