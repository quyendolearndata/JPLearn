"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { AccessState, EmptyState, ErrorState, LoadingState, PageHeading } from "../../../../components/page-states";
import { apiJson } from "../../../../lib/api";
import { type Collection, type CollectionDetail, type SavedScene } from "../../../../lib/feature-types";
import { useSessionUser } from "../../../../lib/use-session-user";

export default function CollectionDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { ready, token } = useSessionUser();
  const [collection, setCollection] = useState<CollectionDetail | null>(null);
  const [name, setName] = useState("");
  const [savedScenes, setSavedScenes] = useState<SavedScene[]>([]);
  const [selectedScene, setSelectedScene] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true); setError("");
    try {
      const [data, saved] = await Promise.all([
        apiJson<CollectionDetail>(`/me/collections/${params.id}`, { token }),
        apiJson<SavedScene[]>("/me/saved-scenes", { token }),
      ]);
      setCollection(data); setName(data.name); setSavedScenes(saved);
    }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Không thể tải bộ sưu tập."); }
    finally { setLoading(false); }
  }, [params.id, token]);
  useEffect(() => { if (token) void load(); else if (ready) setLoading(false); }, [load, ready, token]);

  async function rename(event: FormEvent) {
    event.preventDefault(); if (!token || !collection || !name.trim()) return;
    setBusy(true);
    try {
      await apiJson<Collection>(`/me/collections/${collection.id}`, { method: "PATCH", token, body: JSON.stringify({ expected_revision: collection.revision, name: name.trim() }) });
      await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Không thể đổi tên."); }
    finally { setBusy(false); }
  }

  async function updateScenes(sceneIds: string[]) {
    if (!token || !collection) return;
    setBusy(true);
    try {
      await apiJson<Collection>(`/me/collections/${collection.id}/scenes`, { method: "PUT", token, body: JSON.stringify({ expected_revision: collection.revision, scene_ids: sceneIds }) });
      await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Không thể cập nhật thứ tự cảnh."); }
    finally { setBusy(false); }
  }

  async function deleteCollection() {
    if (!token || !collection || !window.confirm(`Xóa bộ sưu tập “${collection.name}”?`)) return;
    setBusy(true);
    try { await apiJson<null>(`/me/collections/${collection.id}`, { method: "DELETE", token }); router.push("/library"); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Không thể xóa bộ sưu tập."); setBusy(false); }
  }

  if (ready && !token) return <AccessState />;
  if (loading) return <LoadingState />;
  if (error && !collection) return <ErrorState message={error} retry={() => void load()} />;
  if (!collection) return null;
  const ids = collection.scenes.map((scene) => scene.scene_id);
  return (
    <section>
      <Link className="back-link" href="/library">← Thư viện</Link>
      <PageHeading title={collection.name} description={`${collection.scene_count} cảnh · phiên bản ${collection.revision}`} />
      {error ? <ErrorState message={error} /> : null}
      <form className="workspace-card workspace-form" onSubmit={rename}>
        <label htmlFor="rename-collection">Đổi tên</label>
        <div className="inline-actions"><input id="rename-collection" value={name} onChange={(e) => setName(e.target.value)} /><button disabled={busy || !name.trim()}>Lưu tên</button></div>
      </form>
      <h2>Các cảnh</h2>
      <div className="workspace-card workspace-toolbar">
        <label htmlFor="collection-add-scene">Thêm từ cảnh đã lưu<select id="collection-add-scene" value={selectedScene} onChange={(event) => setSelectedScene(event.target.value)}><option value="">Chọn cảnh</option>{savedScenes.filter((scene) => scene.availability === "available" && !ids.includes(scene.scene_id)).map((scene) => <option key={scene.scene_id} value={scene.scene_id}>{scene.title_jp || `Cảnh ${scene.scene_index ?? ""}`}</option>)}</select></label>
        <button disabled={busy || !selectedScene} onClick={() => { void updateScenes([...ids, selectedScene]); setSelectedScene(""); }}>Thêm vào bộ</button>
      </div>
      {collection.scenes.length === 0 ? <EmptyState title="Bộ sưu tập đang trống" body="Thêm cảnh từ màn hình học." /> : (
        <div className="workspace-card">
          {collection.scenes.map((scene, index) => (
            <article className="library-row" key={scene.scene_id}>
              <div><strong lang="ja">{scene.title_jp || `Cảnh ${scene.scene_index ?? index + 1}`}</strong><p className="workspace-meta">{scene.availability}</p></div>
              <div className="inline-actions">
                <button disabled={busy || index === 0} onClick={() => { const next=[...ids]; [next[index-1],next[index]]=[next[index],next[index-1]]; void updateScenes(next); }}>↑</button>
                <button disabled={busy || index === ids.length - 1} onClick={() => { const next=[...ids]; [next[index],next[index+1]]=[next[index+1],next[index]]; void updateScenes(next); }}>↓</button>
                <button disabled={busy} onClick={() => void updateScenes(ids.filter((id) => id !== scene.scene_id))}>Bỏ khỏi bộ</button>
              </div>
            </article>
          ))}
        </div>
      )}
      <div className="workspace-card danger-zone"><h2>Xóa bộ sưu tập</h2><button className="btn-danger" disabled={busy} onClick={() => void deleteCollection()}>Xóa bộ sưu tập</button></div>
    </section>
  );
}
