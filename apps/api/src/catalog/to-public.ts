import type { CatalogItemPublic } from "@jplearn/domain";

export function toPublic(item: {
  id: string;
  ciLevel: number;
  durationSeconds: number;
  mediaType: "video" | "audio";
  topicId: string;
  visualSupport: "high" | "medium" | "low";
  media: { playbackUrl: string | null; hlsUrl: string | null }[];
}): CatalogItemPublic {
  return {
    id: item.id,
    ci_level: item.ciLevel,
    duration_seconds: item.durationSeconds,
    media_type: item.mediaType,
    topic_id: item.topicId,
    visual_support: item.visualSupport,
    playback_url: item.media[0]?.playbackUrl ?? undefined,
    hls_url: item.media[0]?.hlsUrl ?? undefined,
  };
}
