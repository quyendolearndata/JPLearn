"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AccessState, EmptyState, ErrorState, LoadingState, PageHeading } from "../../components/page-states";
import { apiJson } from "../../lib/api";
import { type CapabilitySet, type ContentReport, formatDate } from "../../lib/feature-types";
import { useSessionUser } from "../../lib/use-session-user";

const CATEGORY: Record<string, string> = { audio_quality: "Chất lượng âm thanh", scene_timing: "Thời gian cảnh", visual_mismatch: "Hình ảnh không khớp", too_difficult: "Quá khó", other: "Khác" };

export default function ReportsPage() {
  const { ready, token } = useSessionUser();
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [items, setItems] = useState<ContentReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true); setError("");
    try {
      const caps = await apiJson<CapabilitySet>("/capabilities", { token });
      setEnabled(caps.content_reports_enabled);
      setItems(caps.content_reports_enabled ? await apiJson<ContentReport[]>("/me/content-reports?limit=100", { token }) : []);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Không thể tải báo lỗi."); }
    finally { setLoading(false); }
  }, [token]);
  useEffect(() => { if (token) void load(); else if (ready) setLoading(false); }, [load, ready, token]);
  if (ready && !token) return <AccessState />;
  return (
    <section>
      <PageHeading eyebrow="Phản hồi" title="Báo lỗi của tôi" description="Theo dõi phản hồi về âm thanh, hình ảnh và phân cảnh đã gửi trong lúc học." />
      {loading ? <LoadingState /> : error ? <ErrorState message={error} retry={() => void load()} /> : enabled === false ? <EmptyState title="Báo lỗi nội dung chưa được bật" body="Bạn vẫn có thể tiếp tục học; tính năng sẽ xuất hiện khi đội nội dung sẵn sàng xử lý." /> : items.length === 0 ? <EmptyState title="Bạn chưa gửi báo lỗi" body="Trong màn hình học, mở một cảnh và chọn Báo lỗi khi cần." /> : (
        <div className="workspace-grid">{items.map((report) => <article className="workspace-card" key={report.id}><div className="inline-actions"><span className="status-chip" data-status={report.status}>{report.status}</span><span className="workspace-meta">{CATEGORY[report.category] || report.category}</span></div><h2>{report.description}</h2><p className="workspace-meta">Gửi {formatDate(report.created_at)}</p>{report.public_reply ? <p><strong>Phản hồi:</strong> {report.public_reply}</p> : <p>Đội nội dung chưa có phản hồi công khai.</p>}<Link href={`/session?item_id=${report.catalog_item_id}`}>Mở nội dung</Link></article>)}</div>
      )}
    </section>
  );
}
