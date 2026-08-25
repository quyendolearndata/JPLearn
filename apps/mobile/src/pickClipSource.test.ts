import type { CatalogItemPublic } from "@jplearn/domain";
import { pickClipSource } from "./pickClipSource";

function item(over: Partial<CatalogItemPublic>): CatalogItemPublic {
  return {
    id: "c1",
    ci_level: 0,
    duration_seconds: 30,
    media_type: "video",
    topic_id: "t1",
    visual_support: "high",
    ...over,
  };
}

test("FR-LRN-001 prefers hls_url over playback_url", () => {
  const src = pickClipSource([
    item({ playback_url: "https://cdn/x.mp4", hls_url: "https://cdn/x.m3u8" }),
  ]);
  expect(src).toBe("https://cdn/x.m3u8");
});

test("falls back to playback_url when hls_url is null", () => {
  const src = pickClipSource([item({ playback_url: "https://cdn/x.mp4" })]);
  expect(src).toBe("https://cdn/x.mp4");
});

test("skips items without any source and returns null when none", () => {
  expect(pickClipSource([item({}), item({ playback_url: "https://cdn/y.mp4" })])).toBe(
    "https://cdn/y.mp4",
  );
  expect(pickClipSource([])).toBeNull();
});
