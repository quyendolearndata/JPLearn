"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, parseApiError, parseApiResponse } from "../../lib/api";
import { getToken, getUser, hasRole } from "../../lib/auth-storage";

export interface CatalogItemStaff {
  id: string;
  topic_id: string;
  ci_level: number;
  duration_seconds: number;
  media_type: "video" | "audio";
  visual_support: "high" | "medium" | "low";
  title_internal: string;
  has_l1_translation: false;
  status: "draft" | "level_qa" | "published" | "archived";
  revision: number;
  qa_round: number;
  reviews?: { id: string; qa_round: number; decision: "approve" | "reject"; notes: string; reviewed_by: string; reviewed_at: string }[];
}

const TOPIC_LABELS: Record<string, string> = {
  daily_home: "Sinh hoạt gia đình",
  food: "Ẩm thực & Nấu ăn",
  body: "Cơ thể & Sức khoẻ",
  go_somewhere: "Đi lại & Di chuyển",
  nature: "Thiên nhiên & Đời sống",
  people: "Con người & Giao tiếp",
};

const STATUS_LABELS: Record<string, { label: string; badgeClass: string }> = {
  draft: { label: "Bản nháp", badgeClass: "badge-outline opacity-80" },
  level_qa: { label: "Chờ kiểm duyệt QA", badgeClass: "badge-warning" },
  published: { label: "Đã xuất bản", badgeClass: "badge-success" },
  archived: { label: "Lưu trữ", badgeClass: "badge-outline" },
};

export default function StaffCatalogListPage() {
  const [authorized, setAuthorized] = useState<boolean | null>(null);
  const [items, setItems] = useState<CatalogItemStaff[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [ciLevelFilter, setCiLevelFilter] = useState<string>("all");

  // Check auth and role
  useEffect(() => {
    const isStaff = hasRole("teacher") || hasRole("admin");
    setAuthorized(isStaff);
  }, []);

  const fetchItems = useCallback(async () => {
    const token = getToken();
    if (!token) return;

    setLoading(true);
    setErrorMsg(null);

    const params = new URLSearchParams();
    if (statusFilter !== "all") params.set("status", statusFilter);
    if (ciLevelFilter !== "all") params.set("ci_level", ciLevelFilter);
    params.set("limit", "100");

    const queryStr = params.toString() ? `?${params.toString()}` : "";

    try {
      const res = await api(`/staff/catalog${queryStr}`, { token });
      if (!res.ok) {
        const err = await parseApiError(res);
        setErrorMsg(err.message);
        return;
      }
      const data = await parseApiResponse<{ items: CatalogItemStaff[] }>(res);
      setItems(data?.items || []);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Không thể tải danh sách nội dung.");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, ciLevelFilter]);

  useEffect(() => {
    if (authorized) {
      void fetchItems();
    }
  }, [authorized, fetchItems]);

  if (authorized === false) {
    return (
      <div className="container py-12 max-w-xl mx-auto text-center space-y-4">
        <div className="w-12 h-12 rounded-full bg-rose-500/10 text-rose-400 flex items-center justify-center mx-auto text-2xl">
          ✕
        </div>
        <h1 className="text-2xl font-bold text-foreground">Không có quyền truy cập</h1>
        <p className="text-sm text-muted">
          Khu vực quản trị CMS chỉ dành riêng cho tài khoản có vai trò Giáo viên (teacher) hoặc Quản trị viên (admin).
        </p>
        <div>
          <Link href="/login" className="btn btn-secondary text-sm">
            Đăng nhập tài khoản khác
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="container py-8 space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="badge badge-primary text-xs">Staff CMS</span>
            <span className="text-xs text-muted">Hệ thống biên tập & kiểm duyệt bài học</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground">
            Quản trị nội dung CI
          </h1>
          <p className="text-muted text-sm mt-1">
            Tạo, cập nhật bản nháp, tải lên media MP4 và nộp kiểm định chất lượng thụ đắc.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => void fetchItems()}
            disabled={loading}
            className="btn btn-secondary text-xs"
          >
            {loading ? "Đang tải..." : "Làm mới"}
          </button>
          <Link href="/staff/new" className="btn btn-primary text-sm shadow-md shadow-sky-500/10">
            + Tạo bài học mới
          </Link>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="card p-4 bg-card border border-border rounded-xl flex flex-wrap items-center gap-4 text-xs">
        <div className="flex items-center gap-2">
          <label htmlFor="statusFilter" className="text-muted font-medium">Trạng thái:</label>
          <select
            id="statusFilter"
            aria-label="Lọc theo trạng thái"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="input text-xs py-1 px-2.5 bg-background"
          >
            <option value="all">Tất cả trạng thái</option>
            <option value="draft">Bản nháp (draft)</option>
            <option value="level_qa">Chờ duyệt (level_qa)</option>
            <option value="published">Đã xuất bản (published)</option>
            <option value="archived">Lưu trữ (archived)</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label htmlFor="ciLevelFilter" className="text-muted font-medium">Cấp độ CI:</label>
          <select
            id="ciLevelFilter"
            aria-label="Lọc theo cấp độ CI"
            value={ciLevelFilter}
            onChange={(e) => setCiLevelFilter(e.target.value)}
            className="input text-xs py-1 px-2.5 bg-background"
          >
            <option value="all">Tất cả cấp độ</option>
            <option value="0">Cấp 0 (Mới bắt đầu)</option>
            <option value="1">Cấp 1</option>
            <option value="2">Cấp 2</option>
            <option value="3">Cấp 3</option>
            <option value="4">Cấp 4 (Nâng cao)</option>
          </select>
        </div>

        <div className="ml-auto text-muted">
          Tổng cộng: <strong className="text-foreground">{items.length}</strong> bài học
        </div>
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

      {/* Table of items */}
      {loading ? (
        <div className="py-12 text-center text-muted text-sm card border border-border">
          Đang tải danh sách bài học...
        </div>
      ) : items.length === 0 ? (
        <div className="card p-8 bg-card border border-border rounded-xl text-center space-y-3">
          <p className="text-foreground font-medium">Không tìm thấy bài học nào phù hợp với bộ lọc.</p>
          <p className="text-xs text-muted">Hãy tạo bài học mới hoặc thay đổi tiêu chí lọc.</p>
          <div>
            <Link href="/staff/new" className="btn btn-primary text-xs">
              Tạo bài học đầu tiên
            </Link>
          </div>
        </div>
      ) : (
        <div className="card bg-card border border-border rounded-xl overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="table w-full text-left text-xs">
              <thead>
                <tr className="border-b border-border bg-muted/10 text-muted uppercase tracking-wider font-semibold">
                  <th className="py-3 px-4">Tiêu đề nội bộ</th>
                  <th className="py-3 px-4">Chủ đề</th>
                  <th className="py-3 px-4">Cấp CI</th>
                  <th className="py-3 px-4">Thời lượng</th>
                  <th className="py-3 px-4">Thị giác</th>
                  <th className="py-3 px-4">Trạng thái</th>
                  <th className="py-3 px-4">Phiên bản</th>
                  <th className="py-3 px-4 text-right">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((item) => {
                  const statusInfo = STATUS_LABELS[item.status] || {
                    label: item.status,
                    badgeClass: "badge-outline",
                  };
                  return (
                    <tr key={item.id} className="hover:bg-muted/5 transition-colors">
                      <td className="py-3 px-4 font-medium text-foreground">
                        <Link
                          href={`/staff/${item.id}`}
                          className="hover:text-primary transition-colors"
                        >
                          {item.title_internal}
                        </Link>
                      </td>
                      <td className="py-3 px-4 text-muted">
                        {TOPIC_LABELS[item.topic_id] || item.topic_id}
                      </td>
                      <td className="py-3 px-4">
                        <span className="badge badge-outline text-[11px]">
                          CI-{item.ci_level}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-muted font-mono">{item.duration_seconds}s</td>
                      <td className="py-3 px-4 capitalize text-muted">{item.visual_support}</td>
                      <td className="py-3 px-4">
                        <span className={`badge ${statusInfo.badgeClass} text-[11px]`}>
                          {statusInfo.label}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-muted font-mono">v{item.revision}</td>
                      <td className="py-3 px-4 text-right">
                        <Link
                          href={`/staff/${item.id}`}
                          className="btn btn-secondary text-[11px] py-1 px-3"
                        >
                          Chi tiết / Sửa
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
