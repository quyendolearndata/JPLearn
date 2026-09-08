"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { AccessState, ErrorState, LoadingState, PageHeading } from "../../../../components/page-states";
import { apiJson } from "../../../../lib/api";
import { type StaffSeriesDetail } from "../../../../lib/feature-types";
import { useSessionUser } from "../../../../lib/use-session-user";

type CatalogOption = { id: string; title_internal: string; status: string };

export default function StaffSeriesDetailPage() {
  const params = useParams<{ id: string }>();
  const { ready, token, isStaff, user } = useSessionUser();
  const [series, setSeries] = useState<StaffSeriesDetail | null>(null);
  const [catalog, setCatalog] = useState<CatalogOption[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [selectedItem, setSelectedItem] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true); setError("");
    try {
      const [detail, catalogData] = await Promise.all([
        apiJson<StaffSeriesDetail>(`/staff/series/${params.id}`, { token }),
        apiJson<{ items: CatalogOption[] }>("/staff/catalog?limit=100", { token }),
      ]);
      setSeries(detail); setTitle(detail.title); setDescription(detail.description); setCatalog(catalogData.items);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Không thể tải series."); }
    finally { setLoading(false); }
  }, [params.id, token]);
  useEffect(() => { if (token && isStaff) void load(); else if (ready) setLoading(false); }, [isStaff, load, ready, token]);

  async function mutate(path: string, method: "PATCH" | "PUT" | "POST", body: Record<string, unknown>) {
    if (!token || !series) return;
    setBusy(true); setError("");
    try { const next = await apiJson<StaffSeriesDetail>(path, { method, token, body: JSON.stringify(body) }); setSeries(next); setTitle(next.title); setDescription(next.description); }
    catch (cause) { setError(cause instanceof Error ? `${cause.message} Hãy tải lại nếu dữ liệu đã được người khác sửa.` : "Không thể cập nhật series."); }
    finally { setBusy(false); }
  }
  function saveMetadata(event: FormEvent) { event.preventDefault(); if (series) void mutate(`/staff/series/${series.id}`, "PATCH", { expected_revision: series.revision, title: title.trim(), description: description.trim() }); }
  function saveItems(ids: string[]) { if (series) void mutate(`/staff/series/${series.id}/items`, "PUT", { expected_revision: series.revision, item_ids: ids }); }
  function action(name: string) {
    if (!series) return;
    const body: Record<string, unknown> = { expected_revision: series.revision };
    if (name === "return-to-draft") body.reason = window.prompt("Lý do trả về bản nháp") || "Cần chỉnh sửa thêm";
    void mutate(`/staff/series/${series.id}/${name}`, "POST", body);
  }

  if (ready && (!token || !isStaff)) return <AccessState staff />;
  if (loading) return <LoadingState />;
  if (!series) return <ErrorState message={error || "Không tìm thấy series."} retry={() => void load()} />;
  const ids = series.items.map((item) => item.catalog_item_id);
  const isAdmin = Boolean(user?.roles.includes("admin"));
  return (
    <section>
      <Link className="back-link" href="/staff/series">← Danh sách series</Link>
      <PageHeading eyebrow="Biên tập Series" title={series.title} description={`Revision ${series.revision}`} actions={<span className="status-chip" data-status={series.status}>{series.status}</span>} />
      {error ? <ErrorState message={error} retry={() => void load()} /> : null}
      <form className="workspace-card workspace-form" onSubmit={saveMetadata}><h2>Thông tin</h2><label htmlFor="series-edit-title">Tên series</label><input id="series-edit-title" value={title} onChange={(e) => setTitle(e.target.value)} /><label htmlFor="series-edit-description">Mô tả</label><textarea id="series-edit-description" rows={4} value={description} onChange={(e) => setDescription(e.target.value)} /><button disabled={busy || !title.trim()}>Lưu thông tin</button></form>
      <section className="workspace-card"><h2>Thứ tự tập</h2>{series.items.map((item, index) => { const label=catalog.find((entry) => entry.id===item.catalog_item_id)?.title_internal || item.catalog_item_id; return <div className="library-row" key={item.catalog_item_id}><span><strong>{index+1}. {label}</strong></span><div className="inline-actions"><button disabled={busy || index===0} onClick={() => { const next=[...ids]; [next[index-1],next[index]]=[next[index],next[index-1]]; saveItems(next); }}>↑</button><button disabled={busy || index===ids.length-1} onClick={() => { const next=[...ids]; [next[index],next[index+1]]=[next[index+1],next[index]]; saveItems(next); }}>↓</button><button disabled={busy} onClick={() => saveItems(ids.filter((id) => id!==item.catalog_item_id))}>Bỏ</button></div></div>; })}<div className="field-row"><div><label htmlFor="series-add-item">Thêm bài học</label><select id="series-add-item" value={selectedItem} onChange={(e) => setSelectedItem(e.target.value)}><option value="">Chọn bài học</option>{catalog.filter((item) => !ids.includes(item.id)).map((item) => <option key={item.id} value={item.id}>{item.title_internal} · {item.status}</option>)}</select></div><div className="inline-actions"><button disabled={busy || !selectedItem} onClick={() => { saveItems([...ids,selectedItem]); setSelectedItem(""); }}>Thêm vào cuối</button></div></div></section>
      <section className="workspace-card"><h2>Workflow</h2><div className="inline-actions">{series.status === "draft" ? <button disabled={busy || ids.length===0} onClick={() => action("submit-qa")}>Nộp QA</button> : null}{series.status === "level_qa" && isAdmin ? <><button className="btn-primary" disabled={busy} onClick={() => action("publish")}>Xuất bản</button><button disabled={busy} onClick={() => action("return-to-draft")}>Trả về bản nháp</button></> : null}{series.status === "published" && isAdmin ? <button className="btn-danger" disabled={busy} onClick={() => action("unpublish")}>Gỡ xuất bản</button> : null}</div></section>
    </section>
  );
}
