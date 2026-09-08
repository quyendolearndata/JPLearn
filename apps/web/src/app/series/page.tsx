"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AccessState, EmptyState, ErrorState, LoadingState, PageHeading } from "../../components/page-states";
import { apiJson } from "../../lib/api";
import { type SeriesSummary } from "../../lib/feature-types";
import { useSessionUser } from "../../lib/use-session-user";

export default function SeriesPage() {
  const { ready, token } = useSessionUser();
  const [items, setItems] = useState<SeriesSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true); setError("");
    try { setItems(await apiJson<SeriesSummary[]>("/series", { token })); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Không thể tải series."); }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => { if (token) void load(); else if (ready) setLoading(false); }, [load, ready, token]);
  if (ready && !token) return <AccessState />;

  return (
    <section>
      <PageHeading eyebrow="Học theo mạch" title="Series" description="Xem các clip theo thứ tự tự nhiên để giữ ngữ cảnh và nhịp tiếp xúc tiếng Nhật." />
      {loading ? <LoadingState label="Đang tải series…" /> : error ? <ErrorState message={error} retry={() => void load()} /> : items.length === 0 ? (
        <EmptyState title="Chưa có series đã xuất bản" body="Bạn vẫn có thể học từng clip trong Catalog." />
      ) : (
        <div className="workspace-grid">
          {items.map((series) => (
            <article className="workspace-card" key={series.id}>
              <p className="workspace-eyebrow">CI {series.ci_level} · {series.topic_id}</p>
              <h2>{series.title}</h2>
              <p>{series.description || "Chuỗi nội dung nghe nhìn theo cùng một ngữ cảnh."}</p>
              <p className="workspace-meta">{series.available_item_count} tập đang có</p>
              <Link className="btn-cta" href={`/series/${series.id}`}>Xem series</Link>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
