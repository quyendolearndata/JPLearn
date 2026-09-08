"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ApiResponseError, apiJson } from "../../../../lib/api";
import type { ContentJob, LanguageAnalysisJob, StaffContentVersion, StaffScene, TranscriptRevision } from "../../../../lib/feature-types";
import { useSessionUser } from "../../../../lib/use-session-user";
import { AccessState, ErrorState, LoadingState, PageHeading } from "../../../../components/page-states";

type EditableScene = Omit<StaffScene, "id"> & { id?: string };

export default function ContentStudioPage() {
  const params = useParams<{ id: string }>();
  const itemId = params.id;
  const session = useSessionUser();
  const [content, setContent] = useState<StaffContentVersion | null>(null);
  const [scenes, setScenes] = useState<EditableScene[]>([]);
  const [transcript, setTranscript] = useState<TranscriptRevision | null>(null);
  const [transcriptTexts, setTranscriptTexts] = useState<Record<string, string>>({});
  const [returnReason, setReturnReason] = useState("");
  const [job, setJob] = useState<ContentJob | null>(null);
  const [analysisJob, setAnalysisJob] = useState<LanguageAnalysisJob | null>(null);
  const [jobTask, setJobTask] = useState<"transcript" | "segmentation">("transcript");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    if (!session.token || !session.isStaff || !itemId) return;
    setLoading(true); setError("");
    try {
      const version = await apiJson<StaffContentVersion>(`/staff/catalog/${itemId}/content`, { token: session.token });
      setContent(version); setScenes(version.scenes);
      try {
        const currentTranscript = await apiJson<TranscriptRevision>(`/staff/catalog/${itemId}/transcript?content_version_id=${encodeURIComponent(version.id)}`, { token: session.token });
        setTranscript(currentTranscript);
        setTranscriptTexts(Object.fromEntries(currentTranscript.segments.map((segment) => [segment.scene_id, segment.text_ja])));
      } catch (err) {
        if (err instanceof ApiResponseError && err.status === 404) {
          setTranscript(null);
          setTranscriptTexts(Object.fromEntries(version.scenes.map((scene) => [scene.id, scene.transcript_jp])));
        }
        else throw err;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể tải content studio.");
    } finally { setLoading(false); }
  }, [itemId, session.isStaff, session.token]);

  useEffect(() => void load(), [load]);

  function updateScene(index: number, patch: Partial<EditableScene>) {
    setScenes((current) => current.map((scene, sceneIndex) => sceneIndex === index ? { ...scene, ...patch } : scene));
  }

  function addScene() {
    const lastEnd = scenes.at(-1)?.end_time_seconds ?? 0;
    setScenes((current) => [...current, { scene_index: current.length, start_time_seconds: lastEnd, end_time_seconds: lastEnd + 5, title_jp: "", transcript_jp: "" }]);
  }

  async function saveScenes() {
    if (!session.token || !content) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const updated = await apiJson<StaffContentVersion>(`/staff/catalog/${itemId}/content`, {
        method: "PUT", token: session.token,
        body: JSON.stringify({ version_revision: content.revision, scenes: scenes.map((scene, index) => ({ scene_index: index, start_time_seconds: scene.start_time_seconds, end_time_seconds: scene.end_time_seconds, title_jp: scene.title_jp, transcript_jp: scene.transcript_jp })) }),
      });
      const previousScenes = content.scenes;
      setTranscriptTexts(Object.fromEntries(updated.scenes.map((scene, index) => [scene.id, transcriptTexts[previousScenes[index]?.id] ?? scenes[index]?.transcript_jp ?? scene.transcript_jp])));
      setContent(updated); setScenes(updated.scenes); setNotice(`Đã lưu ${updated.scenes.length} cảnh ở revision ${updated.revision}.`);
    } catch (err) { setError(err instanceof Error ? err.message : "Không thể lưu scenes."); }
    finally { setBusy(false); }
  }

  async function saveTranscript() {
    if (!session.token || !content) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const segments = content.scenes.map((scene) => ({ scene_id: scene.id, text_ja: transcriptTexts[scene.id] ?? scene.transcript_jp }));
      const updated = await apiJson<TranscriptRevision>(`/staff/catalog/${itemId}/transcript`, {
        method: "PUT", token: session.token,
        body: JSON.stringify({ content_version_id: content.id, expected_revision: transcript?.revision ?? 0, segments, provenance: "manual_teacher" }),
      });
      setTranscript(updated); setNotice(`Đã lưu transcript revision ${updated.revision}.`);
    } catch (err) { setError(err instanceof Error ? err.message : "Không thể lưu transcript."); }
    finally { setBusy(false); }
  }

  async function transcriptAction(action: "submit-qa" | "approve" | "return-to-draft") {
    if (!session.token || !content || !transcript) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const updated = await apiJson<TranscriptRevision>(`/staff/catalog/${itemId}/transcript/${action}`, {
        method: "POST", token: session.token,
        body: JSON.stringify({ content_version_id: content.id, expected_revision: transcript.revision, ...(action === "return-to-draft" ? { reason: returnReason } : {}) }),
      });
      setTranscript(updated); setNotice(`Transcript hiện ở trạng thái ${updated.status}.`);
    } catch (err) { setError(err instanceof Error ? err.message : "Không thể chuyển trạng thái transcript."); }
    finally { setBusy(false); }
  }

  async function createJob() {
    if (!session.token || !content) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const created = await apiJson<ContentJob>(`/staff/catalog/${itemId}/content-jobs`, { method: "POST", token: session.token, headers: { "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify({ content_version_id: content.id, task: jobTask, language: "ja" }) });
      setJob(created); setNotice("Đã đưa content job vào hàng đợi.");
    } catch (err) { setError(err instanceof Error ? err.message : "Không thể tạo content job."); }
    finally { setBusy(false); }
  }

  async function runLanguageAnalysis(refresh = false) {
    if (!session.token || !transcript) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const value = refresh && analysisJob
        ? await apiJson<LanguageAnalysisJob>(`/staff/language-analysis-jobs/${analysisJob.id}`, { token: session.token })
        : await apiJson<LanguageAnalysisJob>(`/staff/catalog/${itemId}/language-analysis-jobs`, { method: "POST", token: session.token, headers: { "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify({ transcript_revision_id: transcript.id }) });
      setAnalysisJob(value); setNotice(refresh ? "Đã làm mới trạng thái phân tích." : "Đã đưa phân tích ngôn ngữ vào hàng đợi.");
    } catch (err) { setError(err instanceof Error ? err.message : "Không thể xử lý language analysis job."); }
    finally { setBusy(false); }
  }

  if (!session.ready || loading) return <LoadingState label="Đang tải content studio…" />;
  if (!session.isStaff) return <AccessState staff />;

  return <main className="workspace-shell">
    <PageHeading eyebrow="Staff · FR-SCN-001 · FR-JPA-001" title="Scenes & transcript" description="Tách cảnh, biên tập transcript tiếng Nhật và chuyển qua workflow QA." actions={<Link className="btn btn-secondary" href={`/staff/${itemId}`}>Về bài học</Link>} />
    {error && <ErrorState message={error} retry={() => void load()} />}{notice && <p className="status-success" role="status">{notice}</p>}
    {!content ? <section className="workspace-empty"><h2>Chưa có content version</h2><p>Hãy tải media trong chi tiết bài học trước khi biên tập scenes.</p></section> : <>
      <section className="workspace-card stack-md">
        <div className="workspace-card-header"><div><p className="eyebrow">Content version {content.version_number}</p><h2>Phân cảnh</h2></div><span className="status-chip">rev {content.revision}</span></div>
        {scenes.map((scene, index) => <fieldset className="workspace-card stack-md" key={scene.id ?? index}><legend>Cảnh {index + 1}</legend><div className="workspace-grid"><label>Bắt đầu (s)<input type="number" min={0} value={scene.start_time_seconds} onChange={(event) => updateScene(index, { start_time_seconds: Number(event.target.value) })} /></label><label>Kết thúc (s)<input type="number" min={0} value={scene.end_time_seconds} onChange={(event) => updateScene(index, { end_time_seconds: Number(event.target.value) })} /></label></div><label>Tiêu đề Nhật<input lang="ja" value={scene.title_jp} onChange={(event) => updateScene(index, { title_jp: event.target.value })} /></label><label>Transcript Nhật<textarea lang="ja" rows={3} value={scene.transcript_jp} onChange={(event) => updateScene(index, { transcript_jp: event.target.value })} /></label><button type="button" className="btn btn-secondary" onClick={() => setScenes((current) => current.filter((_, i) => i !== index))}>Xóa cảnh</button></fieldset>)}
        <div className="button-row"><button className="btn btn-secondary" onClick={addScene}>Thêm cảnh</button><button className="btn btn-primary" disabled={busy || content.is_frozen} onClick={() => void saveScenes()}>Lưu scenes</button></div>
      </section>
      <section className="workspace-card stack-md">
        <div className="workspace-card-header"><h2>Transcript revision</h2><span className="status-chip">{transcript ? `${transcript.status} · rev ${transcript.revision}` : "chưa tạo"}</span></div>
        <p>Transcript draft gắn từng đoạn tiếng Nhật với scene đã lưu. Mỗi lần ghi dùng revision để tránh ghi đè thay đổi mới hơn.</p>
        {content.scenes.map((scene, index) => <label key={scene.id}>Cảnh {index + 1} · {scene.title_jp}<textarea lang="ja" rows={3} maxLength={500} value={transcriptTexts[scene.id] ?? ""} onChange={(event) => setTranscriptTexts((current) => ({ ...current, [scene.id]: event.target.value }))} /></label>)}
        <div className="button-row"><button className="btn btn-primary" disabled={busy || content.scenes.length === 0} onClick={() => void saveTranscript()}>Lưu transcript draft</button>{transcript?.status === "draft" || transcript?.status === "returned_to_draft" ? <button className="btn btn-secondary" disabled={busy} onClick={() => void transcriptAction("submit-qa")}>Nộp QA</button> : null}{session.user?.roles.includes("admin") && transcript?.status === "qa_submitted" ? <button className="btn btn-primary" disabled={busy} onClick={() => void transcriptAction("approve")}>Duyệt transcript</button> : null}</div>
        {session.user?.roles.includes("admin") && transcript?.status === "qa_submitted" && <div className="danger-zone"><label>Lý do trả lại<input value={returnReason} onChange={(event) => setReturnReason(event.target.value)} /></label><button className="btn btn-secondary" disabled={busy || !returnReason.trim()} onClick={() => void transcriptAction("return-to-draft")}>Trả về draft</button></div>}
        {transcript && <div className="workspace-card"><h3>Phân tích tiếng Nhật</h3><div className="button-row"><button className="btn btn-secondary" disabled={busy} onClick={() => void runLanguageAnalysis(false)}>Tạo language analysis job</button>{analysisJob && <button disabled={busy} onClick={() => void runLanguageAnalysis(true)}>Làm mới trạng thái</button>}</div>{analysisJob && <><p className="mono-data">{analysisJob.id} · {analysisJob.status}</p>{analysisJob.error_message && <ErrorState message={analysisJob.error_message} />}{analysisJob.results && <details><summary>Kết quả phân tích</summary><pre className="mono-data">{JSON.stringify(analysisJob.results, null, 2)}</pre></details>}</>}</div>}
      </section>
      <section className="workspace-card stack-md"><div className="workspace-card-header"><h2>AI draft job</h2><Link href="/staff/jobs">Mở console jobs</Link></div><div className="workspace-toolbar"><label>Tác vụ<select value={jobTask} onChange={(event) => setJobTask(event.target.value as typeof jobTask)}><option value="transcript">Transcript</option><option value="segmentation">Segmentation</option></select></label><button className="btn btn-primary" disabled={busy || content.is_frozen} onClick={() => void createJob()}>Tạo job tiếng Nhật</button></div>{job && <p className="mono-data">Job {job.id} · {job.status}</p>}</section>
    </>}
  </main>;
}
