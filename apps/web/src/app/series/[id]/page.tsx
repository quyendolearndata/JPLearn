"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AccessState, EmptyState, ErrorState, LoadingState, PageHeading } from "../../../components/page-states";
import { apiJson } from "../../../lib/api";
import { formatDuration, type SeriesDetail } from "../../../lib/feature-types";
import { useSessionUser } from "../../../lib/use-session-user";

export default function SeriesDetailPage() {
  const params = useParams<{ id: string }>();
  const { ready, token } = useSessionUser();
  const [series, setSeries] = useState<SeriesDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true); setError("");
    try { setSeries(await apiJson<SeriesDetail>(`/series/${params.id}`, { token })); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Không thể tải series."); }
    finally { setLoading(false); }
  }, [params.id, token]);
  useEffect(() => { if (token) void load(); else if (ready) setLoading(false); }, [load, ready, token]);
  if (ready && !token) return <AccessState />;
  if (loading) return <LoadingState label="Đang tải các tập…" />;
  if (error) return <ErrorState message={error} retry={() => void load()} />;
  if (!series) return null;

  return (
    <section>
      <Link className="back-link" href="/series">← Tất cả series</Link>
      <PageHeading eyebrow={`CI ${series.ci_level} · ${series.topic_id}`} title={series.title} description={series.description} />
      {series.items.length === 0 ? <EmptyState title="Chưa có tập khả dụng" body="Series này chưa có nội dung đã xuất bản." /> : (
        <div className="workspace-grid">
          {series.items.map((item) => (
            <article className="workspace-card" key={item.catalog_item_id}>
              <p className="workspace-eyebrow">Tập {item.position}</p>
              <h2>{item.topic_id}</h2>
              <p className="workspace-meta">CI {item.ci_level} · {formatDuration(item.duration_seconds)}</p>
              <Link className="btn-cta btn-primary" href={`/session?item_id=${item.catalog_item_id}`}>Học tập này</Link>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
