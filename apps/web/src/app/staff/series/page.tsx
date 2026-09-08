"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { AccessState, EmptyState, ErrorState, LoadingState, PageHeading } from "../../../components/page-states";
import { apiJson } from "../../../lib/api";
import { type StaffSeriesDetail, type StaffSeriesSummary } from "../../../lib/feature-types";
import { useSessionUser } from "../../../lib/use-session-user";

const TOPICS = ["daily_home", "food", "body", "go_somewhere", "nature", "people"];

export default function StaffSeriesPage() {
  const { ready, token, isStaff } = useSessionUser();
  const [items, setItems] = useState<StaffSeriesSummary[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [level, setLevel] = useState("0");
  const [topic, setTopic] = useState(TOPICS[0]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true); setError("");
    try { setItems(await apiJson<StaffSeriesSummary[]>("/staff/series?limit=100", { token })); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Không thể tải series."); }
    finally { setLoading(false); }
  }, [token]);
  useEffect(() => { if (token && isStaff) void load(); else if (ready) setLoading(false); }, [isStaff, load, ready, token]);

  async function create(event: FormEvent) {
    event.preventDefault(); if (!token || !title.trim()) return;
    setBusy(true); setError("");
    try {
      await apiJson<StaffSeriesDetail>("/staff/series", { method: "POST", token, body: JSON.stringify({ title: title.trim(), description: description.trim(), ci_level: level, topic_id: topic }) });
      setTitle(""); setDescription(""); await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Không thể tạo series."); }
    finally { setBusy(false); }
  }

  if (ready && (!token || !isStaff)) return <AccessState staff />;
  return (
    <section>
      <PageHeading eyebrow="Staff" title="Quản lý Series" description="Tạo chuỗi, sắp thứ tự các clip và đưa series qua kiểm duyệt trước khi xuất bản." />
      {error ? <ErrorState message={error} retry={() => void load()} /> : null}
      <form className="workspace-card workspace-form" onSubmit={create}>
        <h2>Tạo series mới</h2>
        <div className="field-row"><div><label htmlFor="series-title">Tên series</label><input id="series-title" value={title} maxLength={100} onChange={(e) => setTitle(e.target.value)} /></div><div><label htmlFor="series-topic">Chủ đề</label><select id="series-topic" value={topic} onChange={(e) => setTopic(e.target.value)}>{TOPICS.map((value) => <option key={value}>{value}</option>)}</select></div><div><label htmlFor="series-level">Cấp CI</label><select id="series-level" value={level} onChange={(e) => setLevel(e.target.value)}>{[0,1,2,3,4].map((value) => <option key={value} value={value}>{value}</option>)}</select></div></div>
        <div><label htmlFor="series-description">Mô tả</label><textarea id="series-description" value={description} maxLength={1000} rows={3} onChange={(e) => setDescription(e.target.value)} /></div>
        <button disabled={busy || !title.trim()}>{busy ? "Đang tạo…" : "Tạo bản nháp"}</button>
      </form>
      <h2>Các series</h2>
      {loading ? <LoadingState /> : items.length === 0 ? <EmptyState title="Chưa có series" body="Tạo series đầu tiên bằng biểu mẫu phía trên." /> : (
        <div className="workspace-table-wrap"><table className="workspace-table"><thead><tr><th>Series</th><th>CI</th><th>Trạng thái</th><th>Số tập</th><th></th></tr></thead><tbody>{items.map((series) => <tr key={series.id}><td><strong>{series.title}</strong><div className="workspace-meta">{series.topic_id}</div></td><td>{series.ci_level}</td><td><span className="status-chip" data-status={series.status}>{series.status}</span></td><td>{series.item_count}</td><td><Link href={`/staff/series/${series.id}`}>Biên tập</Link></td></tr>)}</tbody></table></div>
      )}
    </section>
  );
}
