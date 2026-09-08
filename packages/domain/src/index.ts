export type Role = "learner" | "teacher" | "admin";
export type DeviceClass = "web" | "phone" | "ipad";
export type CiLevel = 0 | 1 | 2 | 3 | 4;
export type MediaType = "video" | "audio";
export type VisualSupport = "high" | "medium" | "low";
export type CatalogStatus = "draft" | "level_qa" | "published" | "archived";
export type EventType =
  | "session_started"
  | "session_ended"
  | "minutes_comprehensible"
  | "level_exposed";

export interface UserPublic {
  id: string;
  email: string;
  roles: Role[];
}

export interface AuthSession {
  access_token: string;
  user: UserPublic;
}

export interface CatalogItemPublic {
  id: string;
  ci_level: number;
  duration_seconds: number;
  media_type: MediaType;
  topic_id: string;
  visual_support: VisualSupport;
  playback_url?: string;
  // NFR-PERF-002: HLS manifest URL when transcoded; clients prefer it and fall back to playback_url (MP4)
  hls_url?: string;
}

export interface LearnerProgress {
  minutes_comprehensible: number;
  current_ci_level: number;
}

export interface Flags {
  speaking_enabled: boolean;
  l1_subtitles_enabled: boolean;
  grammar_enabled: boolean;
  flashcards_enabled: boolean;
}

export const DEFAULT_FLAGS: Flags = {
  speaking_enabled: false,
  l1_subtitles_enabled: false,
  grammar_enabled: false,
  flashcards_enabled: false,
};

export const ZOMBIE_SESSION_SECONDS = 4 * 60 * 60;

export function minutesFromDuration(durationSeconds: number): number {
  if (durationSeconds > ZOMBIE_SESSION_SECONDS) return 0;
  if (durationSeconds < 0) return 0;
  return Math.floor(durationSeconds / 60);
}

// ---------------------------------------------------------------------------
// 1. Content Versions & Scenes (PR1)
// ---------------------------------------------------------------------------

export interface CatalogScenePublic {
  scene_id: string;
  start_ms: number;
  end_ms: number;
  order: number;
}

export interface ContentVersionPublic {
  id: string;
  catalog_item_id: string;
  version_number: number;
  duration_ms: number;
  media_asset_id: string;
  status: "draft" | "level_qa" | "published" | "archived";
  scenes: CatalogScenePublic[];
  created_at: string;
}

export interface CatalogContentDetailPublic {
  catalog_item_id: string;
  content_version_id: string;
  version_number: number;
  duration_ms: number;
  scenes: CatalogScenePublic[];
  playback_url?: string;
  hls_url?: string;
}

// ---------------------------------------------------------------------------
// 2. Series (PR2)
// ---------------------------------------------------------------------------

export interface SeriesPublic {
  id: string;
  title: string;
  description: string;
  topic_id: string;
  ci_level: CiLevel;
  status: "draft" | "level_qa" | "published" | "archived";
  total_items: number;
  available_item_count: number;
  created_at: string;
  updated_at: string;
}

export interface SeriesItemPublic {
  catalog_item_id: string;
  position: number;
  ci_level: CiLevel;
  duration_seconds: number;
  topic_id: string;
}

export interface SeriesDetailPublic extends SeriesPublic {
  items: SeriesItemPublic[];
}

// ---------------------------------------------------------------------------
// 3. Saved Scenes & Personal Collections (PR3, PR3a)
// ---------------------------------------------------------------------------

export type SceneAvailability = "available" | "stale_version" | "unavailable";

export interface SavedScenePublic {
  id: string;
  scene_id: string;
  catalog_item_id: string;
  content_version_id: string;
  start_ms: number;
  end_ms: number;
  order: number;
  saved_at: string;
  availability: SceneAvailability;
}

export interface PersonalCollectionPublic {
  id: string;
  name: string;
  scene_count: number;
  revision: number;
  created_at: string;
  updated_at: string;
}

export interface PersonalCollectionDetailPublic extends PersonalCollectionPublic {
  scenes: SavedScenePublic[];
}

// ---------------------------------------------------------------------------
// 4. Content Reports (PR3b)
// ---------------------------------------------------------------------------

export type ContentReportCategory =
  | "audio_quality"
  | "scene_timing"
  | "visual_mismatch"
  | "too_difficult"
  | "other";

export type ContentReportStatus =
  | "open"
  | "in_review"
  | "resolved"
  | "dismissed";

export interface ContentReportPublic {
  id: string;
  catalog_item_id: string;
  content_version_id: string;
  scene_id?: string | null;
  position_ms?: number | null;
  category: ContentReportCategory;
  description: string;
  status: ContentReportStatus;
  public_reply?: string | null;
  resolution_version_id?: string | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// 5. Playback Tracking & Checkpoints (PR4)
// ---------------------------------------------------------------------------

export type PlaybackPlayerState = "playing" | "paused" | "buffering" | "ended";

export interface PlaybackSessionPublic {
  id: string;
  catalog_item_id: string;
  content_version_id: string;
  epoch: number;
  last_seq: number;
  active_watch_seconds: number;
  heartbeat_interval_seconds: number;
  server_time: string;
}

export interface PlaybackCheckpointInput {
  epoch: number;
  position_ms: number;
  cumulative_active_ms: number;
  player_state: PlaybackPlayerState;
  playback_rate: number;
}

export interface PlaybackCheckpointReceipt {
  accepted_delta_ms: number;
  total_active_ms: number;
  server_time: string;
  checkpoint: {
    position_ms: number;
    updated_at: string;
  };
}

export interface ResumeItemPublic {
  catalog_item_id: string;
  content_version_id: string;
  position_ms: number;
  duration_ms: number;
  completed: boolean;
  last_played_at: string;
  availability: SceneAvailability;
}

// ---------------------------------------------------------------------------
// 6. Learning Preferences, Activity & Watch History (PR5)
// ---------------------------------------------------------------------------

export interface LearningPolicyPublic {
  daily_goal_minutes: number;
  timezone: string;
  effective_at: string;
}

export interface LearningPreferencesPublic {
  current_policy?: LearningPolicyPublic | null;
  pending_policy?: LearningPolicyPublic | null;
  daily_goal_minutes: number;
  preferred_topic_ids: string[];
  timezone: string;
  revision: number;
  effective_at: string;
  created_at: string;
  updated_at: string;
}

export interface UpdateLearningPreferencesBody {
  expected_revision: number;
  daily_goal_minutes?: number | null;
  preferred_topic_ids?: string[] | null;
  timezone?: string | null;
}

export interface DailyActivityItemPublic {
  date: string;
  timezone: string;
  policy_revision: number;
  active_ms: number;
  active_watch_seconds: number;
  goal_minutes: number;
  goal_seconds: number;
  goal_met: boolean;
  updated_at: string;
}

export interface LearnerActivityResponsePublic {
  items: DailyActivityItemPublic[];
  total_active_watch_seconds: number;
  days_goal_met: number;
  current_streak_days: number;
  longest_streak_days: number;
}

export interface WatchHistoryItemPublic {
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
}

export interface WatchHistoryResponsePublic {
  items: WatchHistoryItemPublic[];
  next_cursor?: string | null;
}

export interface HistoryDeletionCreatedPublic {
  deletion_id: string;
  cutoff_time: string;
  status: "queued" | "running" | "completed" | "failed";
  message: string;
}

export interface HistoryDeletionStatusPublic {
  deletion_id: string;
  user_id: string;
  cutoff_time: string;
  status: "queued" | "running" | "completed" | "failed";
  records_deleted: number;
  attempts: number;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}

// ---------------------------------------------------------------------------
// 7. Recommendations (PR6)
// ---------------------------------------------------------------------------

export type RecommendationReason =
  | "same_level"
  | "preferred_topic"
  | "continue_series"
  | "editor_pick";

export interface RecommendedItemPublic {
  catalog_item_id: string;
  media_type: string;
  topic_id: string;
  duration_seconds: number;
  ci_level: number;
  reason: RecommendationReason;
  title_jp?: string | null;
  series_id?: string | null;
  series_title?: string | null;
}

export interface RecommendationsResponsePublic {
  items: RecommendedItemPublic[];
  strategy_version: string;
}

export interface Capabilities {
  video_scene_breakdown_enabled: boolean;
  smart_stream_enabled: boolean;
  interactive_dual_subs_enabled: boolean;
  immersion_lookup_enabled: boolean;
  personal_collections_enabled: boolean;
  content_reports_enabled: boolean;
  playback_tracking_enabled: boolean;
  scene_search_enabled: boolean;
  staff_ai_enabled: boolean;
}

// ---------------------------------------------------------------------------
// 8. Transcripts & Search Projections (PR8a, PR8b)
// ---------------------------------------------------------------------------

export interface TranscriptSegment {
  scene_id: string;
  text_ja: string;
  start_ms?: number;
  end_ms?: number;
}

export interface TranscriptRevisionPublic {
  id: string;
  catalog_item_id: string;
  content_version_id: string;
  revision: number;
  status: "draft" | "level_qa" | "approved" | "archived";
  segments: TranscriptSegment[];
  provenance: string;
  created_at: string;
}

export interface SceneSearchItemPublic {
  catalog_item_id: string;
  content_version_id: string;
  scene_id: string;
  start_time_seconds: number;
  end_time_seconds: number;
  scene_index: number;
  matched_text: string;
  match_kind: "exact" | "token";
  highlights: [number, number][];
}

export interface SceneSearchResponsePublic {
  items: SceneSearchItemPublic[];
  next_cursor?: string | null;
  total_matches?: number;
  generation: string;
}

// ---------------------------------------------------------------------------
// 9. AI Quota Accounts & Usage Ledger (PR8c)
// ---------------------------------------------------------------------------

export interface AiUsageRecordPublic {
  id: string;
  job_id?: string | null;
  kind: "reservation" | "settlement" | "release" | "reconciliation";
  status: "pending" | "settled" | "released" | "outcome_unknown";
  audio_seconds: number;
  input_tokens: number;
  output_tokens: number;
  cost_micros: number;
  currency: string;
  provider: string;
  created_at: string;
}

export interface AiUsageSummaryPublic {
  from_date: string;
  to_date: string;
  total_audio_seconds: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_micros: number;
  currency: string;
}

// ---------------------------------------------------------------------------
// 10. AI Content Jobs Queue (PR8)
// ---------------------------------------------------------------------------

export type ContentJobTask = "transcript" | "segmentation";
export type ContentJobStatus =
  | "queued"
  | "leased"
  | "succeeded"
  | "failed"
  | "cancelled";

export interface ContentJobResponsePublic {
  id: string;
  catalog_item_id: string;
  content_version_id: string;
  task: ContentJobTask;
  language: string;
  status: ContentJobStatus;
  progress: number;
  attempt: number;
  max_attempts: number;
  result_draft?: Record<string, unknown> | null;
  last_error?: string | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// 11. Capabilities (Runtime feature switches)
// ---------------------------------------------------------------------------

export interface CapabilitiesResponsePublic {
  content_scenes: boolean;
  saved_scenes: boolean;
  personal_collections: boolean;
  content_reports: boolean;
  playback_tracking: boolean;
  activity: boolean;
  recommendations: boolean;
  staff_ai: boolean;
  staff_language_tools: boolean;
  scene_search: boolean;
  staff_ai_usage: boolean;
}
