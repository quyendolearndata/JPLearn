"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api, parseApiError, parseApiResponse } from "../../../lib/api";
import { getToken, getUser, hasRole } from "../../../lib/auth-storage";
import type { CatalogItemStaff } from "../page";

const isMp4 = (f: File) => f.name.toLowerCase().endsWith(".mp4") && (f.type === "" || f.type === "video/mp4");

const TOPICS = [
  { id: "daily_home", label: "Sinh hoạt gia đình" },
  { id: "food", label: "Ẩm thực & Nấu ăn" },
  { id: "body", label: "Cơ thể & Sức khoẻ" },
  { id: "go_somewhere", label: "Đi lại & Di chuyển" },
  { id: "nature", label: "Thiên nhiên & Đời sống" },
  { id: "people", label: "Con người & Giao tiếp" },
];

const STATUS_LABELS: Record<string, { label: string; badgeClass: string; desc: string }> = {
  draft: {
    label: "Bản nháp (draft)",
    badgeClass: "badge-outline",
    desc: "Đang biên tập. Chưa hiển thị cho học viên.",
  },
  level_qa: {
    label: "Chờ kiểm duyệt QA (level_qa)",
    badgeClass: "badge-warning",
    desc: "Đã nộp QA. Đang chờ Quản trị viên kiểm tra sư phạm và xuất bản.",
  },
  published: {
    label: "Đã xuất bản (published)",
    badgeClass: "badge-success",
    desc: "Đang hoạt động trên danh mục học viên.",
  },
  archived: {
    label: "Lưu trữ (archived)",
    badgeClass: "badge-outline opacity-60",
    desc: "Bài học đã được lưu trữ.",
  },
};

function StaffItemDetailContent() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const id = params?.id as string;

  const [authorized, setAuthorized] = useState<boolean | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [item, setItem] = useState<CatalogItemStaff | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [conflictWarning, setConflictWarning] = useState<boolean>(false);

  // Editable draft form state
  const [topicId, setTopicId] = useState("daily_home");
  const [ciLevel, setCiLevel] = useState(0);
  const [durationSeconds, setDurationSeconds] = useState(30);
  const [mediaType, setMediaType] = useState<"video" | "audio">("video");
  const [visualSupport, setVisualSupport] = useState<"high" | "medium" | "low">("high");
  const [titleInternal, setTitleInternal] = useState("");

  // Media upload state
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadingMedia, setUploadingMedia] = useState(false);

  useEffect(() => {
    const isStaff = hasRole("teacher") || hasRole("admin");
    setAuthorized(isStaff);
    setIsAdmin(hasRole("admin"));
  }, []);

  // Display initial query notice if any
  useEffect(() => {
    const uploadErr = searchParams.get("upload_err");
    if (uploadErr) {
      setErrorMsg(`Tạo bản nháp thành công nhưng tải media thất bại: ${uploadErr}`);
    }
  }, [searchParams]);

  // Fetch item details
  const fetchItem = useCallback(async () => {
    const token = getToken();
    if (!token || !id) return;

    setLoading(true);
    setErrorMsg(null);
    setConflictWarning(false);

    try {
      const res = await api(`/staff/catalog/${id}`, { token });
      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message);
      }
      const data = await parseApiResponse<CatalogItemStaff>(res);
      if (data) {
        setItem(data);
        setTopicId(data.topic_id);
        setCiLevel(data.ci_level);
        setDurationSeconds(data.duration_seconds);
        setMediaType(data.media_type);
        setVisualSupport(data.visual_support);
        setTitleInternal(data.title_internal);
      }
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Không thể tải chi tiết bài học.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (authorized) {
      void fetchItem();
    }
  }, [authorized, fetchItem]);

  // Save changes with optimistic locking (revision)
  const handleSaveChanges = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!item || item.status !== "draft") return;
    const token = getToken();
    if (!token) return;

    setActionLoading(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    setConflictWarning(false);

    try {
      const patchBody = {
        revision: item.revision,
        topic_id: topicId,
        ci_level: ciLevel,
        duration_seconds: durationSeconds,
        media_type: mediaType,
        visual_support: visualSupport,
        title_internal: titleInternal.trim(),
      };

      const res = await api(`/staff/catalog/${item.id}`, {
        method: "PATCH",
        token,
        body: JSON.stringify(patchBody),
      });

      if (res.status === 409) {
        setConflictWarning(true);
        throw new Error(
          "Xung đột phiên bản! Bài học đã được chỉnh sửa bởi một phiên làm việc khác. Vui lòng tải lại dữ liệu mới nhất.",
        );
      }

      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message);
      }

      const updated = await parseApiResponse<CatalogItemStaff>(res);
      if (updated) {
        setItem(updated);
        setSuccessMsg(`Đã lưu thay đổi thành công (Phiên bản v${updated.revision}).`);
      }
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Không thể cập nhật bài học.");
    } finally {
      setActionLoading(false);
    }
  };

  // Upload MP4 media
  const handleUploadMedia = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!item || !uploadFile) return;
    const token = getToken();
    if (!token) return;

    if (!isMp4(uploadFile)) {
      setErrorMsg("Chỉ chấp nhận tệp video định dạng MP4 (.mp4).");
      return;
    }

    setUploadingMedia(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const formData = new FormData();
      formData.append("file", uploadFile);

      const res = await api(`/staff/catalog/${item.id}/media`, {
        method: "POST",
        token,
        body: formData,
      });

      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message);
      }

      setSuccessMsg("Tải tệp media lên thành công!");
      setUploadFile(null);
      void fetchItem();
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Tải tệp media thất bại.");
    } finally {
      setUploadingMedia(false);
    }
  };

  // Submit QA
  const handleSubmitQa = async () => {
    if (!item) return;
    const token = getToken();
    if (!token) return;

    setActionLoading(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const res = await api(`/staff/catalog/${item.id}/submit-qa`, {
        method: "POST",
        token,
      });

      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message);
      }

      const updated = await parseApiResponse<CatalogItemStaff>(res);
      if (updated) setItem(updated);
      setSuccessMsg("Đã gửi kiểm định QA thành công. Chờ Quản trị viên phê duyệt.");
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Không thể gửi QA.");
    } finally {
      setActionLoading(false);
    }
  };

  // Admin Publish
  const handlePublish = async () => {
    if (!item) return;
    const token = getToken();
    if (!token) return;

    setActionLoading(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const res = await api(`/staff/catalog/${item.id}/publish`, {
        method: "POST",
        token,
      });

      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message);
      }

      const updated = await parseApiResponse<CatalogItemStaff>(res);
      if (updated) setItem(updated);
      setSuccessMsg("Đã xuất bản bài học thành công! Học viên hiện có thể truy cập qua danh mục.");
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Xuất bản thất bại.");
    } finally {
      setActionLoading(false);
    }
  };

  // Admin Unpublish (back to draft)
  const handleUnpublish = async () => {
    if (!item) return;
    const token = getToken();
    if (!token) return;

    setActionLoading(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const res = await api(`/staff/catalog/${item.id}/unpublish`, {
        method: "POST",
        token,
      });

      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message);
      }

      const updated = await parseApiResponse<CatalogItemStaff>(res);
      if (updated) setItem(updated);
      setSuccessMsg("Đã gỡ xuất bản. Bài học đã trở lại trạng thái Bản nháp để chỉnh sửa.");
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Gỡ xuất bản thất bại.");
    } finally {
      setActionLoading(false);
    }
  };

  if (authorized === false) {
    return (
      <div className="container py-12 max-w-xl mx-auto text-center space-y-4">
        <h1 className="text-2xl font-bold text-foreground">Không có quyền truy cập</h1>
        <p className="text-sm text-muted">Cần vai trò Giáo viên hoặc Quản trị viên.</p>
        <Link href="/login" className="btn btn-secondary text-sm">
          Đăng nhập
        </Link>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="container py-12 text-center text-muted text-sm">
        Đang tải thông tin bài học...
      </div>
    );
  }

  if (!item) {
    return (
      <div className="container py-12 max-w-md mx-auto text-center space-y-4">
        <h1 className="text-xl font-bold text-foreground">Không tìm thấy bài học</h1>
        <p className="text-sm text-muted">Bài học có thể đã bị xoá hoặc bạn không có quyền xem.</p>
        <Link href="/staff" className="btn btn-secondary text-xs">
          Về danh sách CMS
        </Link>
      </div>
    );
  }

  const statusInfo = STATUS_LABELS[item.status] || {
    label: item.status,
    badgeClass: "badge-outline",
    desc: "",
  };

  const isDraft = item.status === "draft";
  const isLevelQa = item.status === "level_qa";
  const isPublished = item.status === "published";

  return (
    <div className="container py-8 max-w-4xl mx-auto space-y-6">
      {/* Breadcrumb & Title */}
      <div className="border-b border-border pb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-muted mb-2">
            <Link href="/staff" className="hover:text-foreground">
              Quản trị CMS
            </Link>
            <span>/</span>
            <span className="font-mono text-muted">#{item.id.slice(0, 8)}</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            {item.title_internal}
          </h1>
          <div className="flex flex-wrap items-center gap-3 mt-2">
            <span className={`badge ${statusInfo.badgeClass} text-xs`}>
              {statusInfo.label}
            </span>
            <span className="text-xs text-muted font-mono">Phiên bản: v{item.revision}</span>
            <span className="text-xs text-muted">
              Hỗ trợ ngôn ngữ: L1 không sử dụng (Thuần ngữ cảnh)
            </span>
          </div>
        </div>

        {/* Action button bar */}
        <div className="flex flex-wrap items-center gap-2">
          {isDraft && (
            <button
              type="button"
              onClick={() => void handleSubmitQa()}
              disabled={actionLoading}
              className="btn btn-primary text-xs"
            >
              {actionLoading ? "Đang gửi..." : "Nộp kiểm định QA"}
            </button>
          )}

          {isLevelQa && isAdmin && (
            <button
              type="button"
              onClick={() => void handlePublish()}
              disabled={actionLoading}
              className="btn btn-success text-xs shadow-md shadow-emerald-500/10"
            >
              {actionLoading ? "Đang xuất bản..." : "Xuất bản bài học"}
            </button>
          )}

          {isPublished && isAdmin && (
            <button
              type="button"
              onClick={() => void handleUnpublish()}
              disabled={actionLoading}
              className="btn btn-danger text-xs"
            >
              {actionLoading ? "Đang xử lý..." : "Gỡ xuất bản (Về nháp)"}
            </button>
          )}

          <Link href="/staff" className="btn btn-secondary text-xs">
            Về danh sách
          </Link>
        </div>
      </div>

      {/* Alerts */}
      {errorMsg && (
        <div className="alert alert-error flex items-start justify-between gap-2">
          <span>{errorMsg}</span>
          <button
            type="button"
            onClick={() => setErrorMsg(null)}
            className="text-xs font-semibold opacity-70 hover:opacity-100"
          >
            Đóng
          </button>
        </div>
      )}

      {conflictWarning && (
        <div className="alert alert-warning flex items-center justify-between gap-3">
          <div className="text-xs">
            <strong>Chú ý:</strong> Dữ liệu đã thay đổi trên máy chủ. Nhấn nút bên cạnh để đồng bộ phiên bản mới nhất.
          </div>
          <button
            type="button"
            onClick={() => void fetchItem()}
            className="btn btn-secondary text-xs py-1 px-3"
          >
            Tải lại dữ liệu
          </button>
        </div>
      )}

      {successMsg && (
        <div className="alert alert-success flex items-start justify-between gap-2">
          <span>{successMsg}</span>
          <button
            type="button"
            onClick={() => setSuccessMsg(null)}
            className="text-xs font-semibold opacity-70 hover:opacity-100"
          >
            Đóng
          </button>
        </div>
      )}

      {/* Status Explanation Card */}
      <div className="card p-4 bg-muted/10 border border-border rounded-xl text-xs text-muted flex items-center gap-3">
        <span className="font-semibold text-foreground">Trạng thái:</span>
        <span>{statusInfo.desc}</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Left 2 Cols: Main Metadata Form */}
        <div className="md:col-span-2 space-y-6">
          <form
            onSubmit={(e) => void handleSaveChanges(e)}
            className="card p-6 bg-card border border-border rounded-xl space-y-5 shadow-sm"
          >
            <div className="flex items-center justify-between border-b border-border pb-3">
              <h2 className="text-base font-bold text-foreground">
                Thông tin sư phạm & biên tập
              </h2>
              {isDraft ? (
                <span className="text-[11px] text-emerald-400 font-medium">Có thể chỉnh sửa</span>
              ) : (
                <span className="text-[11px] text-muted">Chỉ đọc (Đang khoá theo trạng thái)</span>
              )}
            </div>

            {/* Title */}
            <div className="space-y-1.5">
              <label htmlFor="title" className="text-xs font-semibold text-foreground uppercase tracking-wider">
                Tiêu đề nội bộ
              </label>
              <input
                id="title"
                type="text"
                disabled={!isDraft}
                required
                value={titleInternal}
                onChange={(e) => setTitleInternal(e.target.value)}
                className="input w-full text-sm disabled:opacity-60 disabled:cursor-not-allowed"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Topic */}
              <div className="space-y-1.5">
                <label htmlFor="topic" className="text-xs font-semibold text-foreground uppercase tracking-wider">
                  Chủ đề
                </label>
                <select
                  id="topic"
                  disabled={!isDraft}
                  value={topicId}
                  onChange={(e) => setTopicId(e.target.value)}
                  className="input w-full text-sm bg-background disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {TOPICS.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.label} ({t.id})
                    </option>
                  ))}
                </select>
              </div>

              {/* CI Level */}
              <div className="space-y-1.5">
                <label htmlFor="ci" className="text-xs font-semibold text-foreground uppercase tracking-wider">
                  Cấp độ CI (0 - 4)
                </label>
                <select
                  id="ci"
                  disabled={!isDraft}
                  value={ciLevel}
                  onChange={(e) => setCiLevel(Number(e.target.value))}
                  className="input w-full text-sm bg-background disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  <option value={0}>Cấp 0 (Mới bắt đầu)</option>
                  <option value={1}>Cấp 1</option>
                  <option value={2}>Cấp 2</option>
                  <option value={3}>Cấp 3</option>
                  <option value={4}>Cấp 4</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {/* Duration */}
              <div className="space-y-1.5">
                <label htmlFor="duration" className="text-xs font-semibold text-foreground uppercase tracking-wider">
                  Thời lượng (s)
                </label>
                <input
                  id="duration"
                  type="number"
                  disabled={!isDraft}
                  min={1}
                  required
                  value={durationSeconds}
                  onChange={(e) => setDurationSeconds(Math.max(1, Number(e.target.value)))}
                  className="input w-full text-sm font-mono disabled:opacity-60 disabled:cursor-not-allowed"
                />
              </div>

              {/* Media Type */}
              <div className="space-y-1.5">
                <label htmlFor="mediaType" className="text-xs font-semibold text-foreground uppercase tracking-wider">
                  Loại media
                </label>
                <select
                  id="mediaType"
                  disabled={!isDraft}
                  value={mediaType}
                  onChange={(e) => setMediaType(e.target.value as "video" | "audio")}
                  className="input w-full text-sm bg-background disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  <option value="video">Video</option>
                  <option value="audio" disabled>Audio (Q1 chưa hỗ trợ tải tệp audio)</option>
                </select>
              </div>

              {/* Visual Support */}
              <div className="space-y-1.5">
                <label htmlFor="visual" className="text-xs font-semibold text-foreground uppercase tracking-wider">
                  Hỗ trợ thị giác
                </label>
                <select
                  id="visual"
                  disabled={!isDraft}
                  value={visualSupport}
                  onChange={(e) => setVisualSupport(e.target.value as "high" | "medium" | "low")}
                  className="input w-full text-sm bg-background disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  <option value="high">Cao (High)</option>
                  <option value="medium">Trung bình (Medium)</option>
                  <option value="low">Thấp (Low)</option>
                </select>
              </div>
            </div>

            {/* Save Button for Draft */}
            {isDraft && (
              <div className="pt-3 border-t border-border flex items-center justify-between">
                <span className="text-xs text-muted">
                  Khoá kiểm soát phiên bản: <span className="font-mono text-foreground">v{item.revision}</span>
                </span>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="btn btn-primary text-xs"
                >
                  {actionLoading ? "Đang lưu..." : "Lưu thay đổi"}
                </button>
              </div>
            )}
          </form>
        </div>

        {/* Right 1 Col: Media Management & Lifecycle */}
        <div className="space-y-6">
          {/* Media Upload Card */}
          <div className="card p-5 bg-card border border-border rounded-xl space-y-4 shadow-sm">
            <h3 className="text-sm font-bold text-foreground border-b border-border pb-2">
              Tệp đa phương tiện
            </h3>

            {isDraft ? (
              <form onSubmit={(e) => void handleUploadMedia(e)} className="space-y-3">
                <label htmlFor="upload" className="text-xs text-muted block">
                  Tải lên tệp MP4 mới:
                </label>
                <input
                  id="upload"
                  type="file"
                  accept="video/mp4"
                  onChange={(e) => {
                    const file = e.target.files?.[0] || null;
                    if (file && !isMp4(file)) {
                      setErrorMsg("Chỉ chấp nhận tệp video định dạng MP4 (.mp4).");
                      setUploadFile(null);
                      e.target.value = "";
                    } else {
                      setErrorMsg(null);
                      setUploadFile(file);
                    }
                  }}
                  className="input w-full text-xs file:mr-2 file:py-0.5 file:px-2 file:rounded file:border-0 file:text-[11px] file:bg-primary/20 file:text-primary"
                />
                <button
                  type="submit"
                  disabled={uploadingMedia || !uploadFile}
                  className="btn btn-secondary text-xs w-full"
                >
                  {uploadingMedia ? "Đang tải lên..." : "Tải lên tệp MP4"}
                </button>
              </form>
            ) : (
              <p className="text-xs text-muted">
                Tệp media bị khoá không cho tải mới khi bài học đang ở trạng thái {statusInfo.label}.
              </p>
            )}

            <div className="pt-2 border-t border-border text-[11px] text-muted space-y-1 font-mono">
              <div>Mã định danh: {item.id.slice(0, 16)}...</div>
              <div>Bản dịch L1: Không có (Chỉ ngữ cảnh)</div>
            </div>
          </div>

          {/* Quick Info & Guidelines */}
          <div className="card p-5 bg-muted/10 border border-border rounded-xl text-xs space-y-2 text-muted">
            <div className="font-semibold text-foreground">Nguyên tắc kiểm duyệt CI:</div>
            <ul className="list-disc list-inside space-y-1 text-[11px]">
              <li>Nội dung 100% tiếng Nhật qua ngữ cảnh hình ảnh trực tiếp.</li>
              <li>Không chèn giải thích quy tắc từ vựng hay cấu trúc.</li>
              <li>Chất lượng âm thanh chuẩn tự nhiên, không đọc gượng ép.</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function StaffItemDetailPage() {
  return (
    <Suspense
      fallback={
        <div className="container py-12 text-center text-muted text-sm">
          Đang tải chi tiết bài học...
        </div>
      }
    >
      <StaffItemDetailContent />
    </Suspense>
  );
}
