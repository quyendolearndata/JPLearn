import type { CatalogItemPublic } from "@jplearn/domain";
import { signedHlsForAsset, signedPlaybackForAsset } from "../media/signed-url";

export function toPublic(item: {
  id: string;
  ciLevel: number;
  durationSeconds: number;
  mediaType: "video" | "audio";
  topicId: string;
  visualSupport: "high" | "medium" | "low";
  media: { id: string; playbackUrl: string | null; hlsUrl: string | null }[];
}): CatalogItemPublic {
  const asset = item.media[0];
  return {
    id: item.id,
    ci_level: item.ciLevel,
    duration_seconds: item.durationSeconds,
    media_type: item.mediaType,
    topic_id: item.topicId,
    visual_support: item.visualSupport,
    playback_url: asset ? signedPlaybackForAsset(asset.id) : undefined,
    hls_url: asset?.hlsUrl ? signedHlsForAsset(asset.id) : undefined,
  };
}
