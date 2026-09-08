/**
 * PlaybackTracker — Client-side active immersion time & heartbeat manager (ADR-007, PR7).
 *
 * Implements:
 * - Active precision time tracking: records real cumulative milliseconds from HTMLVideoElement events.
 * - Single active playback lease & epoch takeover detection (409 Conflict).
 * - Periodic checkpointing (15s heartbeat) to server with monotonic seq numbers.
 * - Graceful end and resume position reporting.
 */

import { api, parseApiResponse } from "./api";

export interface PlaybackStartResult {
  playbackId: string;
  epoch: number;
  initialPositionMs: number;
  resumePositionMs: number | null;
}

export interface PlaybackTrackerConfig {
  video: HTMLVideoElement;
  catalogItemId: string;
  contentVersionId?: string | null;
  onLeaseConflict?: (message: string) => void;
  onActiveTimeChange?: (cumulativeActiveMs: number) => void;
  heartbeatIntervalMs?: number;
}

function getOrCreateClientId(): string {
  if (typeof window === "undefined") return "server-client-id";
  try {
    let id = sessionStorage.getItem("jplearn.playback.client_id");
    if (!id) {
      id = "web-" + Math.random().toString(36).substring(2, 10) + "-" + Date.now();
      sessionStorage.setItem("jplearn.playback.client_id", id);
    }
    return id;
  } catch {
    return "web-fallback-" + Date.now();
  }
}

const getMonotonicTime = (): number => {
  if (typeof performance !== "undefined" && typeof performance.now === "function") {
    return performance.now();
  }
  return Date.now();
};

export class PlaybackTracker {
  private video: HTMLVideoElement;
  private catalogItemId: string;
  private contentVersionId: string | null;
  private onLeaseConflict?: (message: string) => void;
  private onActiveTimeChange?: (cumulativeActiveMs: number) => void;
  private heartbeatIntervalMs: number;

  private playbackId: string | null = null;
  private epoch = 1;
  private seq = 1;
  private cumulativeActiveMs = 0;
  private lastTickTime: number | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private active = false;
  private checkpointFlight: Promise<boolean> | null = null;
  private pendingCheckpoint: { seq: number; body: string } | null = null;
  private startFlight: Promise<PlaybackStartResult | null> | null = null;
  private pendingStart: { body: string; key: string } | null = null;
  private startResult: PlaybackStartResult | null = null;
  private endFlight: Promise<void> | null = null;
  private pendingEnd: string | null = null;
  private endSnapshot: Record<string, number> | null = null;
  private ending = false;
  private destroyed = false;

  constructor(config: PlaybackTrackerConfig) {
    this.video = config.video;
    this.catalogItemId = config.catalogItemId;
    this.contentVersionId = config.contentVersionId ?? null;
    this.onLeaseConflict = config.onLeaseConflict;
    this.onActiveTimeChange = config.onActiveTimeChange;
    this.heartbeatIntervalMs = config.heartbeatIntervalMs ?? 15000;

    this.attachVideoEvents();
  }

  private attachVideoEvents() {
    this.video.addEventListener("play", this.handlePlay);
    this.video.addEventListener("playing", this.handlePlaying);
    this.video.addEventListener("pause", this.handlePause);
    this.video.addEventListener("waiting", this.handleWaiting);
    this.video.addEventListener("timeupdate", this.handleTick);
    this.video.addEventListener("seeking", this.handleSeeking);
    this.video.addEventListener("seeked", this.handleSeeked);
    this.video.addEventListener("ended", this.handleEnded);
  }

  private detachVideoEvents() {
    this.video.removeEventListener("play", this.handlePlay);
    this.video.removeEventListener("playing", this.handlePlaying);
    this.video.removeEventListener("pause", this.handlePause);
    this.video.removeEventListener("waiting", this.handleWaiting);
    this.video.removeEventListener("timeupdate", this.handleTick);
    this.video.removeEventListener("seeking", this.handleSeeking);
    this.video.removeEventListener("seeked", this.handleSeeked);
    this.video.removeEventListener("ended", this.handleEnded);
  }

  private handlePlay = () => {
    if (this.destroyed || this.ending || !this.active) return;
    this.lastTickTime = getMonotonicTime();
  };

  private handlePlaying = () => {
    if (this.destroyed || this.ending || !this.active) return;
    this.lastTickTime = getMonotonicTime();
  };

  private handlePause = () => {
    this.accumulateDelta();
    this.lastTickTime = null;
  };

  private handleWaiting = () => {
    // Stop recording active study time while video is buffering
    this.accumulateDelta();
    this.lastTickTime = null;
  };

  private handleSeeking = () => {
    this.accumulateDelta();
    this.lastTickTime = null;
  };

  private handleSeeked = () => {
    if (this.destroyed || this.ending || !this.active || this.video.paused) return;
    this.lastTickTime = getMonotonicTime();
  };

  private handleEnded = () => {
    this.accumulateDelta();
    this.lastTickTime = null;
    void this.end();
  };

  private handleTick = () => {
    if (this.destroyed || this.video.paused || this.video.seeking) return;
    this.accumulateDelta();
  };

  private accumulateDelta() {
    if (this.lastTickTime === null) return;
    const now = getMonotonicTime();
    const delta = now - this.lastTickTime;
    this.lastTickTime = now;

    // Reject non-positive or unrealistically large jumps (e.g. background throttling > 10s)
    if (delta > 0 && delta < 10000) {
      this.cumulativeActiveMs += delta;
      this.onActiveTimeChange?.(this.cumulativeActiveMs);
    }
  }

  public getCumulativeActiveMs(): number {
    this.accumulateDelta();
    return Math.floor(this.cumulativeActiveMs);
  }

  public start(options?: { takeOver?: boolean }): Promise<PlaybackStartResult | null> {
    if (this.destroyed || this.ending) return Promise.resolve(null);
    if (this.startFlight) return this.startFlight;
    if (this.active) return Promise.resolve(this.startResult);
    this.startFlight = this.startRequest(options).finally(() => {
      this.startFlight = null;
    });
    return this.startFlight;
  }

  private async startRequest(options?: { takeOver?: boolean }): Promise<PlaybackStartResult | null> {
    // An uncertain response must reuse both the key and the exact request body.
    this.pendingStart ??= {
      key: crypto.randomUUID(),
      body: JSON.stringify({
        catalog_item_id: this.catalogItemId,
        content_version_id: this.contentVersionId,
        device_id: getOrCreateClientId(),
        device_info: {
          platform: "web",
          userAgent: typeof navigator !== "undefined" ? navigator.userAgent.slice(0, 50) : "unknown",
        },
        take_over: options?.takeOver ?? false,
      }),
    };
    try {
      const res = await api("/playbacks", {
        method: "POST",
        headers: { "Idempotency-Key": this.pendingStart.key },
        body: this.pendingStart.body,
      });
      if (!res.ok) {
        // A definite rejection allows a new, explicit takeover attempt.
        if (res.status >= 400 && res.status < 500) this.pendingStart = null;
        if (res.status === 409) this.onLeaseConflict?.("Phiên phát đang chạy trên một thiết bị khác.");
        return null;
      }
      const data = await parseApiResponse<{
        playback_id: string;
        epoch: number;
        initial_position_ms: number;
        resume_checkpoint: { position_ms: number } | null;
      }>(res);
      if (!data?.playback_id || typeof data.epoch !== "number") return null;

      this.playbackId = data.playback_id;
      this.epoch = data.epoch;
      this.seq = 1;
      this.cumulativeActiveMs = 0;
      this.active = true;
      this.pendingStart = null;
      this.lastTickTime = this.video.paused || this.destroyed ? null : getMonotonicTime();
      if (!this.destroyed) {
        if (this.heartbeatTimer) clearInterval(this.heartbeatTimer);
        this.heartbeatTimer = setInterval(() => {
          if (this.ending) void this.end();
          else void this.sendCheckpoint();
        }, this.heartbeatIntervalMs);
      }
      this.startResult = {
        playbackId: data.playback_id,
        epoch: data.epoch,
        initialPositionMs: data.initial_position_ms,
        resumePositionMs: data.resume_checkpoint?.position_ms ?? null,
      };
      return this.startResult;
    } catch {
      return null;
    }
  }

  public sendCheckpoint(): Promise<boolean> {
    if (this.checkpointFlight) return this.checkpointFlight;
    if (!this.active || !this.playbackId || this.destroyed) return Promise.resolve(false);
    if (this.ending && !this.pendingCheckpoint) return Promise.resolve(false);

    if (!this.pendingCheckpoint) {
      this.accumulateDelta();
      this.pendingCheckpoint = {
        seq: this.seq,
        body: JSON.stringify({
          position_ms: Math.floor(this.video.currentTime * 1000),
          duration_ms: this.durationMs(),
          playback_rate: this.video.playbackRate || 1.0,
          state: this.video.paused ? "paused" : "playing",
          client_cumulative_active_ms: Math.floor(this.cumulativeActiveMs),
          client_epoch: this.epoch,
        }),
      };
    }
    this.checkpointFlight = this.checkpointRequest().finally(() => {
      this.checkpointFlight = null;
    });
    return this.checkpointFlight;
  }

  private durationMs(): number {
    return Number.isFinite(this.video.duration) ? Math.floor(this.video.duration * 1000) : 0;
  }

  private stopForConflict() {
    this.active = false;
    this.lastTickTime = null;
    if (this.heartbeatTimer) clearInterval(this.heartbeatTimer);
    this.heartbeatTimer = null;
    this.video.pause();
    this.onLeaseConflict?.("Tài khoản của bạn đang phát trên thiết bị khác.");
  }

  private async checkpointRequest(): Promise<boolean> {
    const pending = this.pendingCheckpoint!;
    try {
      const res = await api(`/playbacks/${this.playbackId}/checkpoints/${pending.seq}`, {
        method: "PUT",
        body: pending.body,
      });
      if (res.status === 409) {
        this.stopForConflict();
        return false;
      }
      if (!res.ok) return false;
      this.seq = pending.seq + 1;
      this.pendingCheckpoint = null;
      return true;
    } catch {
      // Retain the exact body: the server may already have committed this seq.
      return false;
    }
  }

  public end(): Promise<void> {
    if (this.endFlight) return this.endFlight;
    if (!this.active || !this.playbackId || this.destroyed) return Promise.resolve();
    if (!this.ending) {
      this.accumulateDelta();
      this.lastTickTime = null;
      this.ending = true;
      this.endSnapshot = {
        final_position_ms: Math.floor(this.video.currentTime * 1000),
        final_duration_ms: this.durationMs(),
        final_playback_rate: this.video.playbackRate || 1.0,
        final_client_cumulative_active_ms: Math.floor(this.cumulativeActiveMs),
        final_client_epoch: this.epoch,
      };
    }
    this.endFlight = this.endRequest().finally(() => {
      this.endFlight = null;
    });
    return this.endFlight;
  }

  private async endRequest(): Promise<void> {
    // Resolve an uncertain checkpoint before assigning the final sequence.
    if (this.checkpointFlight) await this.checkpointFlight;
    if (this.pendingCheckpoint && this.active) await this.sendCheckpoint();
    if (this.pendingCheckpoint || !this.active || this.destroyed) return;
    this.pendingEnd ??= JSON.stringify({ ...this.endSnapshot, final_seq: this.seq });
    try {
      const res = await api(`/playbacks/${this.playbackId}/end`, {
        method: "POST",
        body: this.pendingEnd,
      });
      if (res.status === 409) {
        this.stopForConflict();
        return;
      }
      if (!res.ok) return;
      this.active = false;
      this.pendingEnd = null;
      if (this.heartbeatTimer) clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    } catch {
      // The heartbeat retries this same end payload until ACK while mounted.
    }
  }

  public destroy() {
    this.destroyed = true;
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    this.detachVideoEvents();
  }
}
