"use client";

import { useState } from "react";
import { api } from "../lib/api";

export interface SceneItem {
  id: string;
  scene_index: number;
  start_time_seconds: number;
  end_time_seconds: number;
  title_jp: string;
  transcript_jp: string;
}

interface SceneStripProps {
  catalogItemId: string;
  contentVersionId?: string | null;
  scenes: SceneItem[];
  currentTimeSeconds: number;
  onSeek: (seconds: number) => void;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s < 10 ? "0" : ""}${s}`;
}

export function SceneStrip({
  catalogItemId,
  contentVersionId,
  scenes,
  currentTimeSeconds,
  onSeek,
}: SceneStripProps) {
  const [savedSceneIds, setSavedSceneIds] = useState<Set<string>>(new Set());
  const [savingSceneId, setSavingSceneId] = useState<string | null>(null);
  const [reportingScene, setReportingScene] = useState<SceneItem | null>(null);
  const [reportCategory, setReportCategory] = useState<string>("audio_quality");
  const [reportDescription, setReportDescription] = useState("");
  const [reportSubmitting, setReportSubmitting] = useState(false);
  const [reportSuccess, setReportSuccess] = useState(false);

  if (!scenes || scenes.length === 0) {
    return null;
  }

  const handleSaveScene = async (sceneId: string) => {
    setSavingSceneId(sceneId);
    try {
      const res = await api(`/me/saved-scenes/${sceneId}`, {
        method: "PUT",
      });
      if (res.ok) {
        setSavedSceneIds((prev) => new Set(prev).add(sceneId));
      }
    } catch {
      // Ignore network failure
    } finally {
      setSavingSceneId(null);
    }
  };

  const handleSubmitReport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reportingScene || !reportDescription.trim()) return;

    setReportSubmitting(true);
    const payload = {
      content_version_id: contentVersionId ?? "",
      scene_id: reportingScene.id,
      position_ms: reportingScene.start_time_seconds * 1000,
      category: reportCategory,
      description: reportDescription.trim(),
    };

    try {
      const res = await api(`/catalog/${catalogItemId}/reports`, {
        method: "POST",
        headers: {
          "Idempotency-Key": `rpt-${reportingScene.id}-${Date.now()}`,
        },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        setReportSuccess(true);
        setTimeout(() => {
          setReportingScene(null);
          setReportDescription("");
          setReportSuccess(false);
        }, 1500);
      }
    } catch {
      // Ignore network failure
    } finally {
      setReportSubmitting(false);
    }
  };

  return (
    <div style={{ marginTop: "1rem", borderTop: "2px solid var(--charcoal)", paddingTop: "1rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
        <h3 style={{ fontSize: "1.05rem", fontWeight: 700 }}>
          Phân cảnh ({scenes.length})
        </h3>
        <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
          Bấm vào cảnh để xem lại
        </span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        {scenes.map((scene) => {
          const isActive =
            currentTimeSeconds >= scene.start_time_seconds &&
            currentTimeSeconds < scene.end_time_seconds;
          const isSaved = savedSceneIds.has(scene.id);
          const isSaving = savingSceneId === scene.id;

          return (
            <div
              key={scene.id}
              data-scene-id={scene.id}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "0.6rem 0.85rem",
                borderRadius: "var(--radius-md)",
                border: isActive ? "2px solid var(--charcoal)" : "1px solid var(--border-color)",
                background: isActive ? "var(--bg-subtle)" : "var(--card-bg)",
                boxShadow: isActive ? "var(--shadow-solid)" : "none",
                transition: "all 0.15s ease",
              }}
            >
              <button
                type="button"
                onClick={() => onSeek(scene.start_time_seconds)}
                style={{
                  background: "none",
                  border: "none",
                  textAlign: "left",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "baseline",
                  gap: "0.75rem",
                  flex: 1,
                  fontFamily: "inherit",
                }}
              >
                <span
                  style={{
                    fontSize: "0.8rem",
                    fontWeight: 700,
                    padding: "0.15rem 0.4rem",
                    borderRadius: "var(--radius-sm)",
                    background: isActive ? "var(--charcoal)" : "var(--bg-subtle)",
                    color: isActive ? "#ffffff" : "var(--text)",
                  }}
                >
                  {formatTime(scene.start_time_seconds)}
                </span>
                <span style={{ fontWeight: 600, fontSize: "0.95rem", color: "var(--text)" }}>
                  {scene.title_jp}
                </span>
              </button>

              <div style={{ display: "flex", gap: "0.4rem", alignItems: "center" }}>
                <button
                  type="button"
                  onClick={() => handleSaveScene(scene.id)}
                  disabled={isSaved || isSaving}
                  style={{
                    fontSize: "0.8rem",
                    fontWeight: 600,
                    padding: "0.3rem 0.6rem",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--charcoal)",
                    background: isSaved ? "var(--green)" : "var(--card-bg)",
                    color: isSaved ? "#ffffff" : "var(--charcoal)",
                    cursor: isSaved ? "default" : "pointer",
                  }}
                >
                  {isSaved ? "Đã lưu" : isSaving ? "Đang lưu..." : "Lưu cảnh"}
                </button>

                <button
                  type="button"
                  onClick={() => setReportingScene(scene)}
                  style={{
                    fontSize: "0.8rem",
                    fontWeight: 600,
                    padding: "0.3rem 0.5rem",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid #d1d5db",
                    background: "var(--card-bg)",
                    color: "var(--text-muted)",
                    cursor: "pointer",
                  }}
                >
                  Báo lỗi
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Modal Báo lỗi cảnh */}
      {reportingScene && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.4)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: "1rem",
          }}
        >
          <div
            style={{
              background: "var(--card-bg)",
              border: "2px solid var(--charcoal)",
              borderRadius: "var(--radius-md)",
              boxShadow: "var(--shadow-solid-lg)",
              padding: "1.5rem",
              maxWidth: "480px",
              width: "100%",
            }}
          >
            <h4 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "0.5rem" }}>
              Báo lỗi cảnh: {reportingScene.title_jp}
            </h4>
            <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginBottom: "1rem" }}>
              Thời điểm: {formatTime(reportingScene.start_time_seconds)} - {formatTime(reportingScene.end_time_seconds)}
            </p>

            {reportSuccess ? (
              <div style={{ color: "var(--green)", fontWeight: 700, padding: "1rem 0" }}>
                ✓ Đã gửi phản hồi thành công! Cảm ơn bạn.
              </div>
            ) : (
              <form onSubmit={handleSubmitReport}>
                <div style={{ marginBottom: "1rem" }}>
                  <label htmlFor="report-category" style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, marginBottom: "0.3rem" }}>
                    Loại vấn đề
                  </label>
                  <select
                    id="report-category"
                    value={reportCategory}
                    onChange={(e) => setReportCategory(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "0.5rem",
                      borderRadius: "var(--radius-sm)",
                      border: "1px solid var(--charcoal)",
                      fontFamily: "inherit",
                    }}
                  >
                    <option value="audio_quality">Chất lượng âm thanh</option>
                    <option value="scene_timing">Lệch thời gian phân cảnh</option>
                    <option value="visual_mismatch">Hình ảnh không khớp</option>
                    <option value="too_difficult">Nội dung quá nhanh / khó</option>
                    <option value="other">Vấn đề khác</option>
                  </select>
                </div>

                <div style={{ marginBottom: "1rem" }}>
                  <label htmlFor="report-desc" style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, marginBottom: "0.3rem" }}>
                    Mô tả chi tiết
                  </label>
                  <textarea
                    id="report-desc"
                    required
                    maxLength={1000}
                    rows={3}
                    value={reportDescription}
                    onChange={(e) => setReportDescription(e.target.value)}
                    placeholder="Mô tả cụ thể vấn đề để ban biên tập khắc phục..."
                    style={{
                      width: "100%",
                      padding: "0.5rem",
                      borderRadius: "var(--radius-sm)",
                      border: "1px solid var(--charcoal)",
                      fontFamily: "inherit",
                    }}
                  />
                </div>

                <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
                  <button
                    type="button"
                    onClick={() => setReportingScene(null)}
                    disabled={reportSubmitting}
                    style={{
                      padding: "0.5rem 0.85rem",
                      borderRadius: "var(--radius-sm)",
                      border: "1px solid #d1d5db",
                      background: "#f3f4f6",
                      cursor: "pointer",
                      fontFamily: "inherit",
                    }}
                  >
                    Hủy
                  </button>
                  <button
                    type="submit"
                    disabled={reportSubmitting || !reportDescription.trim()}
                    style={{
                      padding: "0.5rem 1rem",
                      borderRadius: "var(--radius-sm)",
                      border: "1px solid var(--charcoal)",
                      background: "var(--charcoal)",
                      color: "#ffffff",
                      cursor: "pointer",
                      fontWeight: 600,
                      fontFamily: "inherit",
                    }}
                  >
                    {reportSubmitting ? "Đang gửi..." : "Gửi phản hồi"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
