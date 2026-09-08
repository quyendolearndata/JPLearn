"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { AccessState, EmptyState, ErrorState, LoadingState, PageHeading } from "../../components/page-states";
import { apiJson } from "../../lib/api";
import { formatDate, formatDuration, type HistoryDeletion, type HistoryItem, type HistoryPage } from "../../lib/feature-types";
import { useSessionUser } from "../../lib/use-session-user";

export default function HistoryPage() {
  const { ready, token } = useSessionUser();
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [deletion, setDeletion] = useState<HistoryDeletion | null>(null);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async (nextCursor?: string, append = false) => {
    if (!token) return;
    setLoading(true); setError("");
    try {
      const query = nextCursor ? `?limit=20&cursor=${encodeURIComponent(nextCursor)}` : "?limit=20";
      const data = await apiJson<HistoryPage>(`/me/watch-history${query}`, { token });
      setItems((current) => append ? [...current, ...data.items] : data.items);
      setCursor(data.next_cursor ?? null);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Không thể tải lịch sử."); }
    finally { setLoading(false); }
  }, [token]);

  const checkDeletion = useCallback(async (id: string) => {
    if (!token) return;
    try {
      const next = await apiJson<HistoryDeletion>(`/me/history-deletions/${id}`, { token });
      setDeletion(next);
      if (next.status === "completed") { setItems([]); setCursor(null); return; }
      if (next.status !== "failed") pollRef.current = setTimeout(() => void checkDeletion(id), 1500);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Không thể kiểm tra trạng thái xóa."); }
  }, [token]);

  useEffect(() => { if (token) void load(); else if (ready) setLoading(false); return () => { if (pollRef.current) clearTimeout(pollRef.current); }; }, [load, ready, token]);

  async function requestDeletion() {
    if (!token || !window.confirm("Xóa toàn bộ lịch sử xem hiện tại? Tiến độ tích lũy vẫn được giữ lại.")) return;
    setBusy(true); setError("");
    try { const job = await apiJson<HistoryDeletion>("/me/watch-history", { method: "DELETE", token }); setDeletion(job); void checkDeletion(job.deletion_id); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Không thể gửi yêu cầu xóa."); }
    finally { setBusy(false); }
  }

  if (ready && !token) return <AccessState />;
  return (
    <section>
      <PageHeading eyebrow="Hoạt động" title="Lịch sử xem" description="Các phiên xem gần nhất và vị trí bạn đã dừng." actions={<button className="btn-danger" disabled={busy || items.length === 0} onClick={() => void requestDeletion()}>Xóa lịch sử</button>} />
      {deletion ? <div className={deletion.status === "failed" ? "status-error" : "status-notice"}>Yêu cầu xóa: <strong>{deletion.status}</strong>{deletion.records_deleted !== undefined ? ` · ${deletion.records_deleted} bản ghi` : ""}</div> : null}
      {error ? <ErrorState message={error} retry={() => void load()} /> : null}
      {loading && items.length === 0 ? <LoadingState label="Đang tải lịch sử…" /> : items.length === 0 ? <EmptyState title="Chưa có lịch sử xem" body="Bắt đầu một clip trong Catalog để lịch sử xuất hiện ở đây." /> : (
        <div className="workspace-table-wrap">
          <table className="workspace-table"><thead><tr><th>Nội dung</th><th>Vị trí</th><th>Thời gian xem</th><th>Lần cuối</th><th></th></tr></thead><tbody>
            {items.map((item) => <tr key={item.playback_id}><td><strong>{item.title_jp || item.topic_id}</strong><div className="workspace-meta">{item.status}</div></td><td>{formatDuration(Math.round(item.last_position_ms / 1000))} / {formatDuration(item.duration_seconds)}</td><td>{formatDuration(Math.round(item.total_active_ms / 1000))}</td><td>{formatDate(item.updated_at)}</td><td><Link href={`/session?item_id=${item.catalog_item_id}`}>Xem tiếp</Link></td></tr>)}
          </tbody></table>
        </div>
      )}
      {cursor ? <div className="inline-actions"><button disabled={loading} onClick={() => void load(cursor, true)}>{loading ? "Đang tải…" : "Tải thêm"}</button></div> : null}
    </section>
  );
}
