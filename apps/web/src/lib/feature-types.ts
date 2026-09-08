export type CapabilitySet = {
  video_scene_breakdown_enabled: boolean;
  smart_stream_enabled: boolean;
  interactive_dual_subs_enabled: boolean;
  immersion_lookup_enabled: boolean;
  personal_collections_enabled: boolean;
  content_reports_enabled: boolean;
  playback_tracking_enabled: boolean;
  scene_search_enabled: boolean;
  staff_ai_enabled: boolean;
};

export type SeriesSummary = {
  id: string;
  title: string;
  description: string;
  ci_level: string;
  topic_id: string;
  available_item_count: number;
};

export type SeriesClip = {
  catalog_item_id: string;
  position: number;
  topic_id: string;
  ci_level: string;
  duration_seconds: number;
};

export type SeriesDetail = Omit<SeriesSummary, "available_item_count"> & { items: SeriesClip[] };

export type SavedScene = {
  id: string;
  scene_id: string;
  saved_at: string;
  availability: "available" | "stale_version" | "unavailable";
  unavailable_reason?: string | null;
  catalog_item_id?: string | null;
  content_version_id?: string | null;
  scene_index?: number | null;
  start_time_seconds?: number | null;
  end_time_seconds?: number | null;
  title_jp?: string | null;
  transcript_jp?: string | null;
};

export type Collection = {
  id: string;
  name: string;
  revision: number;
  scene_count: number;
  created_at: string;
  updated_at: string;
};

export type CollectionScene = Omit<SavedScene, "id" | "saved_at"> & {
  position: number;
  added_at: string;
};

export type CollectionDetail = Collection & { scenes: CollectionScene[] };

export type HistoryItem = {
  playback_id: string;
  catalog_item_id: string;
  title_jp?: string | null;
  item_type: string;
  topic_id: string;
  duration_seconds: number;
  status: string;
  last_position_ms: number;
  total_active_ms: number;
  content_version_id: string;
  created_at: string;
  updated_at: string;
};

export type HistoryPage = { items: HistoryItem[]; next_cursor?: string | null };

export type HistoryDeletion = {
  deletion_id: string;
  status: "queued" | "running" | "completed" | "failed";
  message?: string;
  records_deleted?: number;
  error_message?: string | null;
};

export type ContentReport = {
  id: string;
  user_id?: string;
  catalog_item_id: string;
  content_version_id: string;
  scene_id?: string | null;
  position_ms: number;
  category: string;
  description: string;
  status: "open" | "in_review" | "resolved" | "dismissed";
  revision?: number;
  assignee_id?: string | null;
  public_reply?: string | null;
  internal_note?: string | null;
  resolution_version_id?: string | null;
  created_at: string;
  updated_at: string;
};

export type StaffSeriesSummary = {
  id: string;
  title: string;
  description: string;
  ci_level: string;
  topic_id: string;
  status: "draft" | "level_qa" | "published" | "unpublished";
  revision: number;
  item_count: number;
  created_at: string;
  updated_at: string;
};

export type StaffSeriesDetail = Omit<StaffSeriesSummary, "item_count"> & {
  items: { catalog_item_id: string; position: number }[];
};

export type TranscriptRevision = {
  id: string;
  catalog_item_id: string;
  content_version_id: string;
  revision: number;
  status: "draft" | "qa_submitted" | "approved" | "returned_to_draft";
  segments: { scene_id: string; text_ja: string }[];
  provenance: "manual_teacher" | "ai_assisted" | "imported";
  created_by: string;
  return_reason?: string | null;
};

export type StaffScene = {
  id: string;
  scene_index: number;
  start_time_seconds: number;
  end_time_seconds: number;
  title_jp: string;
  transcript_jp: string;
};

export type StaffContentVersion = {
  id: string;
  catalog_item_id: string;
  version_number: number;
  revision: number;
  is_frozen: boolean;
  is_published: boolean;
  scenes: StaffScene[];
};

export type ContentReportAudit = {
  id: string;
  report_id: string;
  actor_id: string;
  from_status?: string | null;
  to_status: string;
  revision: number;
  reason?: string | null;
  created_at: string;
};

export type ContentReportDetail = ContentReport & { audit_logs: ContentReportAudit[] };

export type ContentJob = {
  id: string;
  catalog_item_id: string;
  content_version_id: string;
  task: string;
  language: string;
  status: string;
  progress: number;
  provenance: Record<string, unknown>;
  result_draft?: Record<string, unknown> | null;
  error_message?: string | null;
  applied_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type LanguageAnalysisJob = {
  id: string;
  catalog_item_id: string;
  transcript_revision_id: string;
  status: "queued" | "running" | "completed" | "failed";
  results?: Record<string, unknown> | null;
  error_message?: string | null;
  created_at?: string | null;
  completed_at?: string | null;
};

export type AiUsageItem = {
  id: string;
  account_id: string;
  job_id: string;
  kind: string;
  status: string;
  provider: string;
  attempt: number;
  audio_seconds: number;
  input_tokens: number;
  output_tokens: number;
  cost_micros: number;
  currency: string;
  policy_version: string;
  created_at: string;
};

export type AiUsageList = {
  items: AiUsageItem[];
  total_count: number;
  from_date: string;
  to_date: string;
};

export type AiUsageSummary = {
  from_date: string;
  to_date: string;
  summary: Array<{
    provider: string;
    currency: string;
    date: string;
    total_audio_seconds: number;
    total_input_tokens: number;
    total_output_tokens: number;
    total_cost_micros: number;
    events_count: number;
  }>;
  total_audio_seconds: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_micros: number;
};

export function formatDuration(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return minutes ? `${minutes}:${String(rest).padStart(2, "0")}` : `${rest} giây`;
}

export function formatDate(value: string) {
  return new Intl.DateTimeFormat("vi-VN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export function formatMoneyMicros(value: number, currency = "USD") {
  return new Intl.NumberFormat("vi-VN", { style: "currency", currency }).format(value / 1_000_000);
}
