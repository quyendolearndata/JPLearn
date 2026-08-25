import type { CatalogItemPublic } from "@jplearn/domain";

// FR-LRN-001: prefer HLS (hls_url), fall back to MP4 playback_url (NFR-PERF-002)
export function pickClipSource(items: CatalogItemPublic[]): string | null {
  for (const item of items) {
    const source = item.hls_url ?? item.playback_url;
    if (source) return source;
  }
  return null;
}
