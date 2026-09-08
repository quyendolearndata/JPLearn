"use client";

import { useCallback, useEffect, useState } from "react";
import { apiJson, ApiResponseError } from "../../../lib/api";
import type { AiUsageList, AiUsageSummary } from "../../../lib/feature-types";
import { formatDate, formatMoneyMicros } from "../../../lib/feature-types";
import { useSessionUser } from "../../../lib/use-session-user";
import { AccessState, EmptyState, ErrorState, LoadingState, PageHeading } from "../../../components/page-states";

function isoStart(value: string) { return new Date(`${value}T00:00:00`).toISOString(); }
function isoEnd(value: string) { return new Date(`${value}T23:59:59.999`).toISOString(); }

export default function StaffAiUsagePage() {
  const session = useSessionUser();
  const today = new Date().toISOString().slice(0, 10);
  const weekAgo = new Date(Date.now() - 6 * 86400000).toISOString().slice(0, 10);
  const [fromDate, setFromDate] = useState(weekAgo);
  const [toDate, setToDate] = useState(today);
  const [usage, setUsage] = useState<AiUsageList | null>(null);
  const [summary, setSummary] = useState<AiUsageSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!session.token || !session.isStaff) return;
    setLoading(true); setError(""); setSummary(null);
    const query = new URLSearchParams({ from_date: isoStart(fromDate), to_date: isoEnd(toDate) });
    try {
      setUsage(await apiJson<AiUsageList>(`/staff/ai-usage?${query}`, { token: session.token }));
      if (session.user?.roles.includes("admin")) setSummary(await apiJson<AiUsageSummary>(`/staff/ai-usage/summary?${query}`, { token: session.token }));
    } catch (err) {
      if (err instanceof ApiResponseError && err.status === 403) setError("Tính năng AI staff đang tắt hoặc tài khoản chưa đủ quyền.");
      else setError(err instanceof Error ? err.message : "Không thể tải AI usage.");
    } finally { setLoading(false); }
  }, [fromDate, session.isStaff, session.token, session.user?.roles, toDate]);

  useEffect(() => void load(), [load]);
  if (!session.ready) return <LoadingState />;
  if (!session.isStaff) return <AccessState title="Chỉ dành cho staff" message="Bạn cần quyền teacher hoặc admin." />;

  return <main className="workspace-shell">
    <PageHeading eyebrow="Staff · FR-AI-001" title="AI usage" description="Theo dõi lượt gọi, thời lượng âm thanh và chi phí theo pricing policy đã ghi nhận." />
    <div className="workspace-toolbar"><label>Từ ngày<input type="date" value={fromDate} max={toDate} onChange={(event) => setFromDate(event.target.value)} /></label><label>Đến ngày<input type="date" value={toDate} min={fromDate} max={today} onChange={(event) => setToDate(event.target.value)} /></label><button className="btn btn-secondary" onClick={() => void load()}>Làm mới</button></div>
    {error && <ErrorState message={error} />}
    {loading ? <LoadingState /> : <>
      {summary && <section className="workspace-grid"><article className="workspace-card"><small>Tổng chi phí</small><strong>{formatMoneyMicros(summary.total_cost_micros)}</strong></article><article className="workspace-card"><small>Audio đã xử lý</small><strong>{summary.total_audio_seconds}s</strong></article><article className="workspace-card"><small>Tokens</small><strong>{summary.total_input_tokens + summary.total_output_tokens}</strong></article></section>}
      {!usage || usage.items.length === 0 ? <EmptyState title="Chưa có AI usage" description="Không có ledger entry trong khoảng thời gian đã chọn." /> : <div className="library-list">{usage.items.map((item) => <div className="library-row" key={item.id}><span><strong>{item.kind} · {item.provider}</strong><small>{formatDate(item.created_at)} · attempt {item.attempt}</small></span><span><strong>{formatMoneyMicros(item.cost_micros, item.currency)}</strong><small>{item.audio_seconds}s · {item.status}</small></span></div>)}</div>}
    </>}
  </main>;
}
