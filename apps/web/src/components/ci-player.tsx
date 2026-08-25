"use client";

import { useEffect, useRef } from "react";
import type Hls from "hls.js";

// NFR-PERF-002: phát hls_url khi có (Safari native, hls.js cho Chrome/Firefox),
// luôn rơi về playback_url (MP4) khi hls_url vắng hoặc HLS lỗi nặng.
export function CiPlayer({
  hlsUrl,
  playbackUrl,
}: {
  hlsUrl?: string | null;
  playbackUrl?: string | null;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const useMp4 = () => {
      if (playbackUrl && video.src !== playbackUrl) {
        video.src = playbackUrl;
      }
    };

    if (!hlsUrl) {
      useMp4();
      return;
    }

    if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = hlsUrl;
      video.addEventListener("error", useMp4);
      return () => video.removeEventListener("error", useMp4);
    }

    let hls: Hls | null = null;
    let cancelled = false;
    void import("hls.js").then(({ default: HlsCtor }) => {
      if (cancelled) return;
      if (!HlsCtor.isSupported()) {
        useMp4();
        return;
      }
      hls = new HlsCtor();
      hls.on(HlsCtor.Events.ERROR, (_event, data) => {
        if (!data.fatal) return;
        hls?.destroy();
        hls = null;
        useMp4();
      });
      hls.loadSource(hlsUrl);
      hls.attachMedia(video);
    });

    return () => {
      cancelled = true;
      hls?.destroy();
    };
  }, [hlsUrl, playbackUrl]);

  return (
    <video
      ref={videoRef}
      controls
      playsInline
      style={{ width: "100%", maxWidth: "40rem" }}
    />
  );
}
