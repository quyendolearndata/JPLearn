-- NFR-PERF-002: optional HLS playback URL per asset; MP4 playback_url stays as fallback
ALTER TABLE "media_assets" ADD COLUMN "hls_url" TEXT;
