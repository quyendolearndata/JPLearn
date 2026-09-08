"use client";

import Link from "next/link";
import { useState } from "react";
import { apiJson } from "../../../lib/api";
import type { ContentJob } from "../../../lib/feature-types";
import { formatDate } from "../../../lib/feature-types";
import { useSessionUser } from "../../../lib/use-session-user";
import { AccessState, ErrorState, LoadingState, PageHeading } from "../../../components/page-states";

export default function StaffJobsPage() {
  const session = useSessionUser();
  const [jobId, setJobId] = useState("");
  const [job, setJob] = useState<ContentJob | null>(null);
  const [expectedRevision, setExpectedRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run(action: "get" | "cancel" | "apply") {
    if (!session.token || !jobId.trim()) return;
    setBusy(true);
    setError("");
    try {
      const suffix = action === "get" ? "" : `/${action}`;
      const value = await apiJson<ContentJob>(`/staff/content-jobs/${jobId.trim()}${suffix}`, {
        method: action === "get" ? "GET" : "POST",
        token: session.token,
        body: action === "apply" ? JSON.stringify({ expected_revision: expectedRevision }) : undefined,
      });
      setJob(value);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể thao tác content job.");
    } finally {
      setBusy(false);
    }
  }

  if (!session.ready) return <LoadingState />;
  if (!session.isStaff) return <AccessState title="Chỉ dành cho staff" message="Bạn cần quyền teacher hoặc admin." />;

  return <main className="workspace-shell">
    <PageHeading eyebrow="Staff · FR-AI-001" title="Content jobs" description="Tra cứu job AI theo ID, hủy job đang chạy hoặc áp dụng bản nháp vào transcript." />
    <section className="workspace-card stack-md">
      <p>Tạo job từ <Link href="/staff">chi tiết bài học</Link> sau khi bài đã có content version và scenes.</p>
      <label>Job ID<input className="mono-data" value={jobId} onChange={(event) => setJobId(event.target.value)} placeholder="UUID của content job" /></label>
      <div className="button-row"><button className="btn btn-primary" disabled={busy || !jobId.trim()} onClick={() => void run("get")}>Tra cứu</button><button className="btn btn-secondary" disabled={busy || !job} onClick={() => void run("cancel")}>Hủy job</button></div>
      {error && <ErrorState message={error} />}
    </section>
    {job && <section className="workspace-card stack-md">
      <div className="workspace-card-header"><h2>{job.task} · {job.language}</h2><span className="status-chip">{job.status}</span></div>
      <p>Tiến độ: {Math.round(job.progress * 100)}% · cập nhật {formatDate(job.updated_at)}</p>
      <p className="mono-data">catalog {job.catalog_item_id}<br />version {job.content_version_id}</p>
      {job.error_message && <ErrorState message={job.error_message} />}
      {job.result_draft && <details><summary>Xem kết quả nháp</summary><pre className="mono-data">{JSON.stringify(job.result_draft, null, 2)}</pre></details>}
      {job.status === "succeeded" && !job.applied_at && <div className="danger-zone"><label>Revision transcript hiện tại<input type="number" min={0} value={expectedRevision} onChange={(event) => setExpectedRevision(Number(event.target.value))} /></label><button className="btn btn-primary" disabled={busy} onClick={() => void run("apply")}>Áp dụng vào transcript draft</button><small>API kiểm tra content source và revision trước khi ghi.</small></div>}
    </section>}
  </main>;
}
