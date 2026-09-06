"use client";

import { useEffect, useRef, useState } from "react";
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
  const shouldResumeRef = useRef(false);
  const [paused, setPaused] = useState(true);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    let disposed = false;
    let trackingSuspended = true;
    let hls: Hls | null = null;
    let removeSourceError = () => {};
    let removeRestorePlayback = () => {};

    const rememberPlayback = () => {
      // Loading another source can emit pause/timeupdate events for its reset
      // position. Keep the snapshot from the source being recovered instead.
      if (trackingSuspended) return;
      if (Number.isFinite(video.currentTime) && video.currentTime > 0) {
        lastPositionRef.current = video.currentTime;
      }
      shouldResumeRef.current = !video.paused;
      setPaused(video.paused);
    };
    video.addEventListener("timeupdate", rememberPlayback);
    video.addEventListener("seeking", rememberPlayback);
    video.addEventListener("play", rememberPlayback);
    video.addEventListener("pause", rememberPlayback);

    const registerRestorePlayback = (shouldResume = shouldResumeRef.current) => {
      removeRestorePlayback();
      const savedPosition = lastPositionRef.current;
      trackingSuspended = true;
      let finished = false;
      const restorePlayback = () => {
        if (disposed || finished || video.readyState < HTMLMediaElement.HAVE_METADATA) return;
        if (savedPosition > 0) {
          const maximum = Number.isFinite(video.duration)
            ? Math.max(0, video.duration - 0.05)
            : savedPosition;
          video.currentTime = Math.min(savedPosition, maximum);
        }
        finished = true;
        video.removeEventListener("loadedmetadata", restorePlayback);
        trackingSuspended = false;
        if (shouldResume) void video.play().catch(() => {});
      };
      video.addEventListener("loadedmetadata", restorePlayback);
      removeRestorePlayback = () => {
        finished = true;
        video.removeEventListener("loadedmetadata", restorePlayback);
      };
    };

    const setSource = (source: string, shouldResume?: boolean) => {
      registerRestorePlayback(shouldResume);
      video.src = source;
    };

    const reportFailure = () => {
      rememberPlayback();
      removeRestorePlayback();
      // Retain this position while the parent fetches replacement signed URLs.
      trackingSuspended = true;
      onSourceFailure?.();
    };

    const useMp4OrReport = (shouldResume?: boolean) => {
      removeSourceError();
      if (!playbackUrl) {
        reportFailure();
        return;
      }
      const onMp4Error = () => reportFailure();
      video.addEventListener("error", onMp4Error);
      removeSourceError = () => video.removeEventListener("error", onMp4Error);
      setSource(playbackUrl, shouldResume);
    };

    if (!hlsUrl) {
      useMp4OrReport();
    } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
      let usingMp4 = false;
      const onNativeError = () => {
        rememberPlayback();
        if (!usingMp4 && playbackUrl) {
          usingMp4 = true;
          useMp4OrReport(shouldResumeRef.current);
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
        let fallbackStarted = false;
        const fallbackFromHls = () => {
          if (fallbackStarted) return;
          fallbackStarted = true;
          rememberPlayback();
          const shouldResume = shouldResumeRef.current;
          trackingSuspended = true;
          hls?.destroy();
          hls = null;
          useMp4OrReport(shouldResume);
        };
        const onHlsMediaError = () => fallbackFromHls();
        video.addEventListener("error", onHlsMediaError);
        removeSourceError = () => video.removeEventListener("error", onHlsMediaError);
        const startPosition = lastPositionRef.current > 0 ? lastPositionRef.current : -1;
        hls = new HlsCtor({ startPosition });
        hls.on(HlsCtor.Events.ERROR, (_event, data) => {
          if (!data.fatal) return;
          fallbackFromHls();
        });
        // A parsed manifest does not imply that the media can seek yet.
        registerRestorePlayback();
        hls.loadSource(hlsUrl);
        hls.attachMedia(video);
      }).catch(() => {
        if (!disposed) useMp4OrReport();
      });
    }

    return () => {
      disposed = true;
      rememberPlayback();
      video.removeEventListener("timeupdate", rememberPlayback);
      video.removeEventListener("seeking", rememberPlayback);
      video.removeEventListener("play", rememberPlayback);
      video.removeEventListener("pause", rememberPlayback);
      removeRestorePlayback();
      removeSourceError();
      hls?.destroy();
    };
  }, [hlsUrl, onSourceFailure, playbackUrl]);

  const togglePlayback = () => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      void video.play().catch(() => {});
    } else {
      video.pause();
    }
  };

  return (
    <div>
      <div style={{ padding: "0.5rem 0.75rem", background: "var(--bg-subtle)" }}>
        <button type="button" tabIndex={0} onClick={togglePlayback} aria-pressed={!paused}>
          {paused ? "Phát" : "Tạm dừng"}
        </button>
      </div>
      <video
        ref={videoRef}
        controls
        playsInline
        tabIndex={-1}
        style={{ width: "100%", maxWidth: "40rem" }}
      />
    </div>
  );
}
