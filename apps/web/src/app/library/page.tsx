"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { AccessState, EmptyState, ErrorState, LoadingState, PageHeading } from "../../components/page-states";
import { apiJson } from "../../lib/api";
import { type CapabilitySet, type Collection, formatDate, type SavedScene } from "../../lib/feature-types";
import { useSessionUser } from "../../lib/use-session-user";

export default function LibraryPage() {
  const { ready, token } = useSessionUser();
  const [caps, setCaps] = useState<CapabilitySet | null>(null);
  const [saved, setSaved] = useState<SavedScene[]>([]);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true); setError("");
    try {
      const capabilities = await apiJson<CapabilitySet>("/capabilities", { token });
      setCaps(capabilities);
      const [scenes, lists] = await Promise.all([
        capabilities.video_scene_breakdown_enabled ? apiJson<SavedScene[]>("/me/saved-scenes", { token }) : Promise.resolve([]),
        capabilities.personal_collections_enabled ? apiJson<Collection[]>("/me/collections", { token }) : Promise.resolve([]),
      ]);
      setSaved(scenes); setCollections(lists);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Không thể tải thư viện."); }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => { if (token) void load(); else if (ready) setLoading(false); }, [load, ready, token]);

  async function createCollection(event: FormEvent) {
    event.preventDefault();
    if (!token || !name.trim()) return;
    setBusy(true); setError("");
    try {
      await apiJson<Collection>("/me/collections", { method: "POST", token, body: JSON.stringify({ name: name.trim() }) });
      setName(""); await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Không thể tạo bộ sưu tập."); }
    finally { setBusy(false); }
  }

  async function removeSaved(sceneId: string) {
    if (!token) return;
    setBusy(true); setError("");
    try { await apiJson<null>(`/me/saved-scenes/${sceneId}`, { method: "DELETE", token }); await load(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Không thể bỏ lưu cảnh."); }
    finally { setBusy(false); }
  }

  if (ready && !token) return <AccessState />;
  return (
    <section>
      <PageHeading eyebrow="Của bạn" title="Thư viện" description="Cảnh đã lưu và các bộ sưu tập ngữ cảnh của riêng bạn." />
      {loading ? <LoadingState label="Đang tải thư viện…" /> : error ? <ErrorState message={error} retry={() => void load()} /> : (
        <div className="workspace-grid">
          <section className="workspace-card">
            <h2>Cảnh đã lưu</h2>
            {!caps?.video_scene_breakdown_enabled ? <p className="workspace-meta">Tính năng phân cảnh chưa được bật.</p> : saved.length === 0 ? (
              <EmptyState title="Chưa lưu cảnh nào" body="Khi học một clip có phân cảnh, chọn Lưu để đưa cảnh vào đây." />
            ) : saved.map((scene) => (
              <article key={scene.id} className="library-row">
                <div>
                  <strong lang="ja">{scene.title_jp || `Cảnh ${scene.scene_index ?? ""}`}</strong>
                  <p className="workspace-meta">{scene.availability} · {formatDate(scene.saved_at)}</p>
                </div>
                <div className="inline-actions">
                  {scene.catalog_item_id ? <Link href={`/session?item_id=${scene.catalog_item_id}`}>Mở cảnh</Link> : null}
                  <button type="button" disabled={busy} onClick={() => void removeSaved(scene.scene_id)}>Bỏ lưu</button>
                </div>
              </article>
            ))}
          </section>
          <section className="workspace-card">
            <h2>Bộ sưu tập</h2>
            {!caps?.personal_collections_enabled ? <p className="workspace-meta">Tính năng bộ sưu tập chưa được bật.</p> : (
              <>
                <form className="workspace-form" onSubmit={createCollection}>
                  <label htmlFor="collection-name">Tên bộ sưu tập</label>
                  <input id="collection-name" value={name} maxLength={100} onChange={(event) => setName(event.target.value)} placeholder="Ví dụ: Đi chợ và nấu ăn" />
                  <button type="submit" disabled={busy || !name.trim()}>Tạo bộ sưu tập</button>
                </form>
                <div className="library-list">
                  {collections.map((collection) => (
                    <Link className="library-row" key={collection.id} href={`/library/collections/${collection.id}`}>
                      <strong>{collection.name}</strong><span>{collection.scene_count} cảnh</span>
                    </Link>
                  ))}
                </div>
              </>
            )}
          </section>
        </div>
      )}
    </section>
  );
}
