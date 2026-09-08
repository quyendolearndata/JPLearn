"use client";

import { useCallback, useEffect, useState } from "react";
import { apiJson } from "../../../lib/api";
import type { ContentReport, ContentReportDetail } from "../../../lib/feature-types";
import { formatDate } from "../../../lib/feature-types";
import { useSessionUser } from "../../../lib/use-session-user";
import { AccessState, EmptyState, ErrorState, LoadingState, PageHeading } from "../../../components/page-states";

const STATUSES = ["open", "in_review", "resolved", "dismissed"] as const;

export default function StaffReportsPage() {
  const session = useSessionUser();
  const [status, setStatus] = useState("");
  const [items, setItems] = useState<ContentReport[]>([]);
  const [selected, setSelected] = useState<ContentReportDetail | null>(null);
  const [publicReply, setPublicReply] = useState("");
  const [internalNote, setInternalNote] = useState("");
  const [nextStatus, setNextStatus] = useState<(typeof STATUSES)[number]>("in_review");
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!session.token || !session.isStaff) return;
    setLoading(true);
    setError("");
    try {
      const query = status ? `?status=${status}` : "";
      setItems(await apiJson<ContentReport[]>(`/staff/content-reports${query}`, { token: session.token }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể tải hàng đợi báo lỗi.");
    } finally {
      setLoading(false);
    }
  }, [session.isStaff, session.token, status]);

  useEffect(() => void load(), [load]);

  async function openReport(id: string) {
    if (!session.token) return;
    setError("");
    try {
      const detail = await apiJson<ContentReportDetail>(`/staff/content-reports/${id}`, { token: session.token });
      setSelected(detail);
      setPublicReply(detail.public_reply ?? "");
      setInternalNote(detail.internal_note ?? "");
      setNextStatus(detail.status);
      setReason("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể tải báo lỗi.");
    }
  }

  async function save() {
    if (!session.token || !selected?.revision) return;
    setSaving(true);
    setError("");
    try {
      await apiJson<ContentReport>(`/staff/content-reports/${selected.id}`, {
        method: "PATCH",
        token: session.token,
        body: JSON.stringify({
          expected_revision: selected.revision,
          status: nextStatus,
          public_reply: publicReply || null,
          internal_note: internalNote || null,
          reason: reason || null,
        }),
      });
      await openReport(selected.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể cập nhật báo lỗi.");
    } finally {
      setSaving(false);
    }
  }

  if (!session.ready) return <LoadingState label="Đang kiểm tra quyền staff…" />;
  if (!session.isStaff) return <AccessState title="Chỉ dành cho staff" message="Đăng nhập bằng tài khoản teacher hoặc admin để xử lý báo lỗi." />;

  return (
    <main className="workspace-shell">
      <PageHeading eyebrow="Staff · FR-RPT-001" title="Báo lỗi nội dung" description="Đọc phản hồi của học viên, cập nhật trạng thái và lưu lịch sử xử lý." />
      <div className="workspace-toolbar">
        <label>Trạng thái <select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">Tất cả</option>{STATUSES.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
        <button className="btn btn-secondary" onClick={() => void load()}>Làm mới</button>
      </div>
      {error && <ErrorState message={error} />}
      {loading ? <LoadingState /> : items.length === 0 ? <EmptyState title="Không có báo lỗi" description="Hàng đợi hiện không có mục phù hợp bộ lọc." /> : (
        <div className="library-list">{items.map((item) => <button className="library-row text-left" key={item.id} onClick={() => void openReport(item.id)}><span><strong>{item.category}</strong><small>{item.description}</small></span><span><span className="status-chip">{item.status}</span><small>{formatDate(item.updated_at)}</small></span></button>)}</div>
      )}
      {selected && <section className="workspace-card stack-md">
        <div className="workspace-card-header"><div><p className="eyebrow">Chi tiết #{selected.id.slice(0, 8)}</p><h2>{selected.category}</h2></div><span className="status-chip">rev {selected.revision}</span></div>
        <p>{selected.description}</p>
        <p className="mono-data">item {selected.catalog_item_id} · {Math.round(selected.position_ms / 1000)}s</p>
        <label>Trạng thái<select value={nextStatus} onChange={(event) => setNextStatus(event.target.value as typeof nextStatus)}>{STATUSES.map((value) => <option key={value}>{value}</option>)}</select></label>
        <label>Phản hồi cho học viên<textarea rows={3} value={publicReply} onChange={(event) => setPublicReply(event.target.value)} /></label>
        <label>Ghi chú nội bộ<textarea rows={3} value={internalNote} onChange={(event) => setInternalNote(event.target.value)} /></label>
        <label>Lý do thay đổi<input value={reason} onChange={(event) => setReason(event.target.value)} /></label>
        <button className="btn btn-primary" disabled={saving} onClick={() => void save()}>{saving ? "Đang lưu…" : "Lưu xử lý"}</button>
        {selected.audit_logs.length > 0 && <details><summary>Lịch sử xử lý ({selected.audit_logs.length})</summary><ul>{selected.audit_logs.map((audit) => <li key={audit.id}>{formatDate(audit.created_at)} · {audit.from_status ?? "new"} → {audit.to_status}{audit.reason ? ` · ${audit.reason}` : ""}</li>)}</ul></details>}
      </section>}
    </main>
  );
}
