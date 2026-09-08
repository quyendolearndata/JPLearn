"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import type { CatalogItemPublic } from "@jplearn/domain";
import { api, parseApiResponse } from "../../lib/api";
import { getToken } from "../../lib/auth-storage";
import { TopicArt } from "../../components/topic-art";

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
  const [query, setQuery] = useState("");

  const visibleItems = items.filter((item) =>
    (TOPIC_LABELS[item.topic_id] ?? item.topic_id)
      .toLocaleLowerCase("vi")
      .includes(query.toLocaleLowerCase("vi"))
  );

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
      <div className="ab-hero catalog-welcome">
        <div className="ab-hero-copy">
          <p className="eyebrow">Nghe · Quan sát · Thấu hiểu</p>
          <h2>Một chút tiếng Nhật.<br/>Một điều mới mỗi ngày.</h2>
          <p>Chọn một câu chuyện vừa sức, bắt đầu từ điều bạn tò mò.</p>
          <a href="#catalog-library" className="btn-cta btn-primary">Khám phá video ↗</a>
        </div>
        <div className="ab-hero-art">
          <TopicArt />
        </div>
      </div>

      <div className="catalog-header-bar" id="catalog-library">
        <div>
          <h1>Catalog</h1>
          <p style={{ color: "var(--text-muted)", fontSize: "0.95rem" }}>
            Hôm nay, bạn muốn khám phá điều gì?
          </p>
        </div>
        <input
          type="search"
          className="catalog-search"
          aria-label="Tìm chủ đề"
          placeholder="Tìm một chủ đề…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />

        <div className="filter-pills" role="group" aria-label="Lọc theo cấp độ CI">
          <button
            type="button"
            className={`filter-pill ${selectedLevel === null ? "active" : ""}`}
            aria-pressed={selectedLevel === null}
            onClick={() => setSelectedLevel(null)}
          >
            Tất cả cấp độ
          </button>
          {[0, 1, 2, 3, 4].map((level) => (
            <button
              key={level}
              type="button"
              className={`filter-pill ${selectedLevel === level ? "active" : ""}`}
              aria-pressed={selectedLevel === level}
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

      {!loading && !errorMessage && visibleItems.length === 0 ? (
        <div style={{ padding: "3rem 1rem", textAlign: "center", background: "#ffffff", border: "2px solid var(--charcoal)", borderRadius: "var(--radius-md)", boxShadow: "var(--shadow-solid)" }}>
          <h3>Chưa có nội dung published</h3>
          <p style={{ color: "var(--text-muted)", marginTop: "0.5rem" }}>
            {selectedLevel !== null
              ? `Hiện chưa có bài học nào ở Cấp ${selectedLevel}. Vui lòng chọn cấp độ khác.`
              : "Hiện tại chưa có clip nào phù hợp với tìm kiếm của bạn."}
          </p>
        </div>
      ) : null}

      <h2 className="sr-only">Danh sách bài học CI</h2>

      {!loading && visibleItems.length > 0 ? (
        <div className="catalog-grid">
          {visibleItems.map((item) => {
            const topicLabel = TOPIC_LABELS[item.topic_id] ?? item.topic_id;
            const visualLabel = VISUAL_SUPPORT_LABELS[item.visual_support] ?? item.visual_support;

            return (
              <article key={item.id} data-item-id={item.id} className="catalog-card">
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
                      {item.duration_seconds} giây
                    </span>
                    <span>{visualLabel}</span>
                  </div>
                </div>

                <div style={{ marginTop: "1rem" }}>
                  <Link
                    href={`/session?item_id=${item.id}`}
                    className="btn-cta btn-primary"
                    style={{ width: "100%", boxSizing: "border-box", textAlign: "center", display: "block" }}
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
