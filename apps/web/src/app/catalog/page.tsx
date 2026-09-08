"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import type {
  CatalogItemPublic,
  RecommendedItemPublic,
  RecommendationsResponsePublic,
  Capabilities,
} from "@jplearn/domain";
import { api, parseApiResponse } from "../../lib/api";
import { getToken, subscribeAuth } from "../../lib/auth-storage";
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

const REASON_TAGS: Record<string, string> = {
  continue_series: "Tiếp tục chuỗi",
  preferred_topic: "Chủ đề yêu thích",
  same_level: "Cùng cấp độ",
  editor_pick: "Gợi ý chọn lọc",
};

export default function CatalogPage() {
  const [items, setItems] = useState<CatalogItemPublic[]>([]);
  const [recommendations, setRecommendations] = useState<RecommendedItemPublic[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingRecs, setLoadingRecs] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [selectedLevel, setSelectedLevel] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);

  const catalogGenRef = useRef(0);
  const recGenRef = useRef(0);

  const visibleItems = items.filter((item) =>
    (TOPIC_LABELS[item.topic_id] ?? item.topic_id)
      .toLocaleLowerCase("vi")
      .includes(query.toLocaleLowerCase("vi"))
  );

  const loadCapabilities = useCallback(async () => {
    const token = getToken();
    if (!token) return;
    try {
      const res = await api("/capabilities", { token });
      if (res.ok) {
        const data = await parseApiResponse<Capabilities>(res);
        setCapabilities(data);
      }
    } catch {
      // Capabilities fallback is non-fatal
    }
  }, []);

  const fetchRecommendations = useCallback(async () => {
    const token = getToken();
    if (!token) {
      setRecommendations([]);
      return;
    }

    const gen = ++recGenRef.current;
    setLoadingRecs(true);

    try {
      const res = await api("/me/recommendations?limit=4", { token });
      if (gen !== recGenRef.current) return;

      if (res.ok) {
        const body = await parseApiResponse<RecommendationsResponsePublic>(res);
        setRecommendations(body?.items ?? []);
      } else {
        setRecommendations([]);
      }
    } catch {
      if (gen === recGenRef.current) {
        setRecommendations([]);
      }
    } finally {
      if (gen === recGenRef.current) {
        setLoadingRecs(false);
      }
    }
  }, []);

  const fetchCatalog = useCallback(async (level: number | null) => {
    const token = getToken();
    const gen = ++catalogGenRef.current;

    if (!token) {
      setLoading(false);
      setErrorMessage("Hãy đăng nhập.");
      setItems([]);
      setRecommendations([]);
      return;
    }

    setLoading(true);
    setErrorMessage("");

    try {
      const path = level !== null ? `/catalog?ci_level=${level}` : "/catalog";
      const res = await api(path, { token });

      if (gen !== catalogGenRef.current) return;

      if (!res.ok) {
        setErrorMessage("Không thể tải danh mục bài học.");
        setItems([]);
        return;
      }

      const body = await parseApiResponse<{ items: CatalogItemPublic[] }>(res);
      setItems(body?.items ?? []);
    } catch {
      if (gen === catalogGenRef.current) {
        setErrorMessage("Lỗi kết nối máy chủ khi tải danh mục.");
        setItems([]);
      }
    } finally {
      if (gen === catalogGenRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void loadCapabilities();
    void fetchRecommendations();

    const unsubscribe = subscribeAuth(() => {
      catalogGenRef.current += 1;
      recGenRef.current += 1;
      void loadCapabilities();
      void fetchRecommendations();
      void fetchCatalog(selectedLevel);
    });

    return () => {
      unsubscribe();
    };
  }, [loadCapabilities, fetchRecommendations, fetchCatalog, selectedLevel]);

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
        <div className="status-error" role="alert">
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

      {/* Recommendations Rail */}
      {!loading && !errorMessage && recommendations.length > 0 && capabilities?.smart_stream_enabled !== false && (
        <section style={{ marginBottom: "2.5rem", marginTop: "1.5rem" }} aria-label="Gợi ý cho bạn">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: "1rem" }}>
            <h2 style={{ fontSize: "1.25rem", fontWeight: 900 }}>Gợi ý cho bạn</h2>
            <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
              Phù hợp với cấp độ CI & lịch sử xem
            </span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: "1rem" }}>
            {recommendations.map((rec) => {
              const reasonTag = REASON_TAGS[rec.reason] || "Gợi ý";
              const topicLabel = TOPIC_LABELS[rec.topic_id] ?? rec.topic_id;

              return (
                <article
                  key={rec.catalog_item_id}
                  data-rec-id={rec.catalog_item_id}
                  style={{
                    background: "var(--card-bg)",
                    border: "2px solid var(--charcoal)",
                    borderRadius: "var(--radius-md)",
                    padding: "1rem",
                    boxShadow: "var(--shadow-solid)",
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-between",
                  }}
                >
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                      <span
                        style={{
                          fontSize: "0.75rem",
                          fontWeight: 700,
                          padding: "0.2rem 0.5rem",
                          borderRadius: "var(--radius-pill)",
                          background: rec.reason === "continue_series" ? "var(--pink)" : "var(--charcoal)",
                          color: "#ffffff",
                        }}
                      >
                        {reasonTag}
                      </span>
                      <span style={{ fontSize: "0.8rem", fontWeight: 700 }}>Cấp {rec.ci_level}</span>
                    </div>

                    <h3 style={{ fontSize: "1rem", fontWeight: 800, marginBottom: "0.25rem" }}>
                      {rec.title_jp || topicLabel}
                    </h3>

                    {rec.series_title && (
                      <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "0.5rem" }}>
                        Chuỗi: {rec.series_title}
                      </p>
                    )}

                    <p style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                      Thời lượng: {rec.duration_seconds}s · {topicLabel}
                    </p>
                  </div>

                  <div style={{ marginTop: "1rem" }}>
                    <Link
                      href={`/session?item_id=${rec.catalog_item_id}`}
                      className="btn-cta btn-primary"
                      style={{ width: "100%", boxSizing: "border-box", textAlign: "center", display: "block", fontSize: "0.85rem", padding: "0.4rem" }}
                    >
                      Xem ngay ↗
                    </Link>
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      )}

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
