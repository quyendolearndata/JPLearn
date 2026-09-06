"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { catalogWriteFields } from "@jplearn/cms-schema";
import { api, parseApiError, parseApiResponse } from "../../../lib/api";
import { getToken, getUser, hasRole } from "../../../lib/auth-storage";

const TOPICS = [
  { id: "daily_home", label: "Sinh hoạt gia đình" },
  { id: "food", label: "Ẩm thực & Nấu ăn" },
  { id: "body", label: "Cơ thể & Sức khoẻ" },
  { id: "go_somewhere", label: "Đi lại & Di chuyển" },
  { id: "nature", label: "Thiên nhiên & Đời sống" },
  { id: "people", label: "Con người & Giao tiếp" },
];

export default function NewCatalogItemPage() {
  const router = useRouter();

  const [authorized, setAuthorized] = useState<boolean | null>(null);
  const [topicId, setTopicId] = useState("daily_home");
  const [ciLevel, setCiLevel] = useState(0);
  const [durationSeconds, setDurationSeconds] = useState(30);
  const [mediaType, setMediaType] = useState<"video" | "audio">("video");
  const [visualSupport, setVisualSupport] = useState<"high" | "medium" | "low">("high");
  const [titleInternal, setTitleInternal] = useState("");
  const [mediaFile, setMediaFile] = useState<File | null>(null);

  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    const isStaff = hasRole("teacher") || hasRole("admin");
    setAuthorized(isStaff);
  }, []);

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = getToken();
    if (!token) return;

    if (!titleInternal.trim()) {
      setErrorMsg("Vui lòng nhập tiêu đề nội bộ của bài học.");
      return;
    }

    setSubmitting(true);
    setErrorMsg(null);

    const body: Record<string, string | number> = {
      topic_id: topicId,
      ci_level: ciLevel,
      duration_seconds: durationSeconds,
      media_type: mediaType,
      visual_support: visualSupport,
      title_internal: titleInternal.trim(),
    };

    // Ensure all required catalogWriteFields are populated
    for (const field of catalogWriteFields) {
      if (!(field in body)) {
        setErrorMsg(`Thiếu trường bắt buộc: ${field}`);
        setSubmitting(false);
        return;
      }
    }

    try {
      // 1. Create draft catalog item
      const res = await api("/staff/catalog", {
        method: "POST",
        token,
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message);
      }

      const created = await parseApiResponse<{ id: string }>(res);
      if (!created?.id) {
        throw new Error("Không nhận được mã định danh bài học.");
      }

      const itemId = created.id;

      // 2. If initial media file is provided, validate and upload it immediately
      if (mediaFile) {
        if (!mediaFile.name.toLowerCase().endsWith(".mp4") && mediaFile.type !== "video/mp4") {
          setErrorMsg("Chỉ chấp nhận tệp video định dạng MP4 (.mp4).");
          setSubmitting(false);
          return;
        }
        const formData = new FormData();
        formData.append("file", mediaFile);

        const mediaRes = await api(`/staff/catalog/${itemId}/media`, {
          method: "POST",
          token,
          body: formData,
        });

        if (!mediaRes.ok) {
          const mediaErr = await parseApiError(mediaRes);
          // Don't fail the whole draft creation, navigate with notice
          router.push(`/staff/${itemId}?upload_err=${encodeURIComponent(mediaErr.message)}`);
          return;
        }
      }

      // Navigate to draft detail/edit screen
      router.push(`/staff/${itemId}`);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Tạo bài học thất bại.");
      setSubmitting(false);
    }
  };

  return (
    <div className="container py-8 max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div className="border-b border-border pb-4">
        <div className="flex items-center gap-2 text-xs text-muted mb-2">
          <Link href="/staff" className="hover:text-foreground">
            Quản trị CMS
          </Link>
          <span>/</span>
          <span className="text-foreground font-medium">Tạo bài học mới</span>
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Tạo bài học mới (Bản nháp)
        </h1>
        <p className="text-sm text-muted mt-1">
          Khai báo thông số sư phạm và gắn tệp đa phương tiện cho bài học tiếng Nhật thụ đắc.
        </p>
      </div>

      {/* Error alert */}
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

      {/* Form */}
      <form onSubmit={(e) => void handleSubmit(e)} className="card p-6 bg-card border border-border rounded-xl space-y-5 shadow-sm">
        {/* Title */}
        <div className="space-y-1.5">
          <label htmlFor="titleInternal" className="text-xs font-semibold text-foreground uppercase tracking-wider">
            Tiêu đề nội bộ *
          </label>
          <input
            id="titleInternal"
            type="text"
            required
            placeholder="Ví dụ: Rót nước vào cốc thuỷ tinh (Mô tả hành động)"
            value={titleInternal}
            onChange={(e) => setTitleInternal(e.target.value)}
            className="input w-full text-sm"
          />
          <p className="text-[11px] text-muted">
            Tiêu đề này chỉ hiển thị trong nội bộ hệ thống biên tập để quản trị, người học sẽ tiếp nhận thuần tuý qua hình ảnh và âm thanh.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Topic */}
          <div className="space-y-1.5">
            <label htmlFor="topicId" className="text-xs font-semibold text-foreground uppercase tracking-wider">
              Chủ đề bài học *
            </label>
            <select
              id="topicId"
              value={topicId}
              onChange={(e) => setTopicId(e.target.value)}
              className="input w-full text-sm bg-background"
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
            <label htmlFor="ciLevel" className="text-xs font-semibold text-foreground uppercase tracking-wider">
              Cấp độ CI (0 - 4) *
            </label>
            <select
              id="ciLevel"
              value={ciLevel}
              onChange={(e) => setCiLevel(Number(e.target.value))}
              className="input w-full text-sm bg-background"
            >
              <option value={0}>Cấp 0 - Hoàn toàn trực quan (Siêu cơ bản)</option>
              <option value={1}>Cấp 1 - Ngữ cảnh trực tiếp</option>
              <option value={2}>Cấp 2 - Mở rộng hành động</option>
              <option value={3}>Cấp 3 - Kể chuyện phức hợp</option>
              <option value={4}>Cấp 4 - Đời sống tự nhiên</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {/* Duration */}
          <div className="space-y-1.5">
            <label htmlFor="durationSeconds" className="text-xs font-semibold text-foreground uppercase tracking-wider">
              Thời lượng (giây) *
            </label>
            <input
              id="durationSeconds"
              type="number"
              min={1}
              required
              value={durationSeconds}
              onChange={(e) => setDurationSeconds(Math.max(1, Number(e.target.value)))}
              className="input w-full text-sm font-mono"
            />
          </div>

          {/* Media Type */}
          <div className="space-y-1.5">
            <label htmlFor="mediaType" className="text-xs font-semibold text-foreground uppercase tracking-wider">
              Định dạng *
            </label>
            <select
              id="mediaType"
              value={mediaType}
              onChange={(e) => setMediaType(e.target.value as "video" | "audio")}
              className="input w-full text-sm bg-background"
            >
              <option value="video">Video</option>
              <option value="audio">Audio</option>
            </select>
          </div>

          {/* Visual Support */}
          <div className="space-y-1.5">
            <label htmlFor="visualSupport" className="text-xs font-semibold text-foreground uppercase tracking-wider">
              Hỗ trợ thị giác *
            </label>
            <select
              id="visualSupport"
              value={visualSupport}
              onChange={(e) => setVisualSupport(e.target.value as "high" | "medium" | "low")}
              className="input w-full text-sm bg-background"
            >
              <option value="high">Cao (High)</option>
              <option value="medium">Trung bình (Medium)</option>
              <option value="low">Thấp (Low)</option>
            </select>
          </div>
        </div>

        {/* Media file upload */}
        <div className="space-y-1.5 border-t border-border pt-4">
          <label htmlFor="mediaFile" className="text-xs font-semibold text-foreground uppercase tracking-wider">
            Tệp Video MP4 (Tuỳ chọn tải ngay)
          </label>
          <input
            id="mediaFile"
            type="file"
            accept="video/mp4"
            onChange={(e) => {
              const file = e.target.files?.[0] || null;
              if (file && !file.name.toLowerCase().endsWith(".mp4") && file.type !== "video/mp4") {
                setErrorMsg("Chỉ chấp nhận tệp video định dạng MP4 (.mp4).");
                setMediaFile(null);
                e.target.value = "";
              } else {
                setErrorMsg(null);
                setMediaFile(file);
              }
            }}
            className="input w-full text-xs file:mr-3 file:py-1 file:px-3 file:rounded-md file:border-0 file:text-xs file:bg-primary/20 file:text-primary hover:file:bg-primary/30"
          />
          <p className="text-[11px] text-muted">
            Bạn có thể tải lên tệp MP4 ngay bây giờ hoặc tải lên sau ở trang chỉnh sửa chi tiết.
          </p>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between pt-4 border-t border-border">
          <Link href="/staff" className="btn btn-secondary text-sm">
            Huỷ bỏ
          </Link>
          <button
            type="submit"
            disabled={submitting}
            className="btn btn-primary text-sm shadow-md shadow-sky-500/10"
          >
            {submitting ? "Đang lưu bài học..." : "Tạo bản nháp bài học"}
          </button>
        </div>
      </form>
    </div>
  );
}
