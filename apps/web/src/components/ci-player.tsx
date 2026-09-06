"use client";

import { useEffect, useRef } from "react";
import type Hls from "hls.js";

// NFR-PERF-002: phát hls_url khi có (Safari native, hls.js cho Chrome/Firefox),
// luôn rơi về playback_url (MP4) khi hls_url vắng hoặc HLS lỗi nặng.
export function CiPlayer({
  hlsUrl,
  playbackUrl,
  onSourceFailure,
}: {
  hlsUrl?: string | null;
  playbackUrl?: string | null;
  onSourceFailure?: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const lastPositionRef = useRef(0);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    if (Number.isFinite(video.currentTime) && video.currentTime > 0) {
      lastPositionRef.current = video.currentTime;
    }
    const shouldResume = !video.paused;
    let disposed = false;
    let hls: Hls | null = null;
    let removeSourceError = () => {};

    const rememberPosition = () => {
      if (Number.isFinite(video.currentTime) && video.currentTime > 0) {
        lastPositionRef.current = video.currentTime;
      }
    };
    video.addEventListener("timeupdate", rememberPosition);
    video.addEventListener("seeking", rememberPosition);

    const restorePlayback = () => {
      if (disposed) return;
      const savedPosition = lastPositionRef.current;
      if (savedPosition > 0) {
        const maximum = Number.isFinite(video.duration)
          ? Math.max(0, video.duration - 0.05)
          : savedPosition;
        video.currentTime = Math.min(savedPosition, maximum);
      }
      if (shouldResume) void video.play().catch(() => {});
    };

    const setSource = (source: string) => {
      video.addEventListener("loadedmetadata", restorePlayback, { once: true });
      video.src = source;
    };

    const reportFailure = () => {
      rememberPosition();
      onSourceFailure?.();
    };

    const useMp4OrReport = () => {
      removeSourceError();
      if (!playbackUrl) {
        reportFailure();
        return;
      }
      const onMp4Error = () => reportFailure();
      video.addEventListener("error", onMp4Error);
      removeSourceError = () => video.removeEventListener("error", onMp4Error);
      setSource(playbackUrl);
    };

    if (!hlsUrl) {
      useMp4OrReport();
    } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
      let usingMp4 = false;
      const onNativeError = () => {
        rememberPosition();
        if (!usingMp4 && playbackUrl) {
          usingMp4 = true;
          setSource(playbackUrl);
          return;
        }
        reportFailure();
      };
      video.addEventListener("error", onNativeError);
      removeSourceError = () => video.removeEventListener("error", onNativeError);
      setSource(hlsUrl);
    } else {
      void import("hls.js").then(({ default: HlsCtor }) => {
        if (disposed) return;
        if (!HlsCtor.isSupported()) {
          useMp4OrReport();
          return;
        }
        hls = new HlsCtor();
        hls.on(HlsCtor.Events.ERROR, (_event, data) => {
          if (!data.fatal) return;
          rememberPosition();
          hls?.destroy();
          hls = null;
          useMp4OrReport();
        });
        hls.loadSource(hlsUrl);
        hls.attachMedia(video);
      }).catch(() => {
        if (!disposed) useMp4OrReport();
      });
    }

    return () => {
      disposed = true;
      rememberPosition();
      video.removeEventListener("timeupdate", rememberPosition);
      video.removeEventListener("seeking", rememberPosition);
      video.removeEventListener("loadedmetadata", restorePlayback);
      removeSourceError();
      hls?.destroy();
    };
  }, [hlsUrl, onSourceFailure, playbackUrl]);

  return (
    <video
      ref={videoRef}
      controls
      playsInline
      style={{ width: "100%", maxWidth: "40rem" }}
    />
  );
}
