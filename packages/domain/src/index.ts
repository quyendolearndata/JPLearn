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
