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

export interface LearningPreferencesPublic {
  timezone: string;
  daily_goal_minutes: number;
  preferred_topic_ids: string[];
  revision: number;
}

export interface DailyActivityBucketPublic {
  day: string; // YYYY-MM-DD
  active_watch_seconds: number;
  goal_seconds: number;
  goal_met: boolean;
  timezone: string;
}

export interface WatchHistoryItemPublic {
  playback_id: string;
  catalog_item_id: string;
  content_version_id: string;
  active_watch_seconds: number;
  started_at: string;
  ended_at?: string | null;
  availability: SceneAvailability;
}

export interface HistoryDeletionPublic {
  id: string;
  status: "queued" | "running" | "completed" | "failed";
  cutoff_time: string;
  created_at: string;
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

export interface RecommendationItemPublic {
  catalog_item_id: string;
  ci_level: CiLevel;
  topic_id: string;
  duration_seconds: number;
  reason: RecommendationReason;
  series_id?: string | null;
}

export interface RecommendationsResponsePublic {
  items: RecommendationItemPublic[];
  strategy_version: string;
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
