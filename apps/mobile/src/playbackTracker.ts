/** FR-WAT-001 / FR-RSM-001: in-memory online tracker; never persists offline telemetry. */
export type Transport = (path: string, init: { method: string; body: string; headers?: Record<string, string> }) => Promise<{ ok: boolean; status: number; json(): Promise<any> }>;
export type Sample = { positionMs: number; durationMs: number; rate: number; playing: boolean; ready: boolean; foreground: boolean };
export class MobilePlaybackTracker {
  private id: string | null = null;
  private epoch = 0;
  private seq = 1;
  private total = 0;
  private previous: { at: number; value: Sample } | null = null;
  private latest: Sample = { positionMs: 0, durationMs: 0, rate: 1, playing: false, ready: false, foreground: true };
  private pendingStart: { key: string; body: string } | null = null;
  private pendingCheckpoint: { seq: number; body: string } | null = null;
  private pendingEnd: string | null = null;
  private startFlight: Promise<number | null> | null = null;
  private flight: Promise<boolean> | null = null;
  private endFlight: Promise<boolean> | null = null;
  private ending = false;
  private stopped = false;
  private resume = 0;
  constructor(private request: Transport, private now: () => number, private uniqueId: () => string, private conflict: () => void) {}
  sample(value: Sample) {
    if (!this.id || this.ending || this.stopped) return;
    const at = this.now();
    if (this.previous) {
      const old = this.previous.value;
      const elapsed = at - this.previous.at;
      const movement = value.positionMs - old.positionMs;
      // Native controls do not expose seeking on all platforms: only count plausible
      // moving intervals. Pauses, buffering, background gaps and seek jumps earn zero.
      if (old.playing && old.ready && old.foreground && value.ready && value.foreground && elapsed > 0 && elapsed <= 2500 && movement > 0 && movement <= elapsed * Math.max(old.rate, value.rate) + 500) {
        this.total += Math.min(elapsed, movement / Math.max(old.rate, 0.25));
      }
    }
    this.latest = value;
    this.previous = { at, value };
  }
  start(itemId: string, versionId: string, deviceClass: "phone" | "ipad", takeOver = false): Promise<number | null> {
    if (this.startFlight) return this.startFlight;
    if (this.id) return Promise.resolve(this.resume);
    this.pendingStart ??= { key: this.uniqueId(), body: JSON.stringify({ catalog_item_id: itemId, content_version_id: versionId, device_id: this.uniqueId(), device_info: { device_class: deviceClass }, take_over: takeOver }) };
    this.startFlight = (async () => {
      try {
        const pending = this.pendingStart!;
        const res = await this.request('/playbacks', { method: 'POST', body: pending.body, headers: { 'Idempotency-Key': pending.key } });
        if (!res.ok) { if (res.status >= 400 && res.status < 500) this.pendingStart = null; return null; }
        const body = await res.json();
        if (!body.playback_id || !Number.isInteger(body.epoch)) return null;
        this.id = body.playback_id; this.epoch = body.epoch; this.resume = body.initial_position_ms ?? 0;
        this.pendingStart = null; return this.resume;
      } catch { return null; }
    })().finally(() => { this.startFlight = null; });
    return this.startFlight;
  }
  private stop() { this.stopped = true; this.previous = null; this.conflict(); }
  checkpoint(): Promise<boolean> {
    if (this.flight) return this.flight;
    if (!this.id || this.stopped || (this.ending && !this.pendingCheckpoint)) return Promise.resolve(false);
    this.pendingCheckpoint ??= { seq: this.seq, body: JSON.stringify({ position_ms: Math.floor(this.latest.positionMs), duration_ms: Math.floor(this.latest.durationMs), playback_rate: this.latest.rate, state: this.latest.playing && this.latest.ready ? 'playing' : 'paused', client_cumulative_active_ms: Math.floor(this.total), client_epoch: this.epoch }) };
    this.flight = (async () => {
      const pending = this.pendingCheckpoint!;
      try {
        const res = await this.request(`/playbacks/${this.id}/checkpoints/${pending.seq}`, { method: 'PUT', body: pending.body });
        if ([400, 403, 404, 409, 422].includes(res.status)) { this.stop(); return false; }
        if (!res.ok) return false;
        this.seq = pending.seq + 1; this.pendingCheckpoint = null; return true;
      } catch { return false; }
    })().finally(() => { this.flight = null; });
    return this.flight;
  }
  end(): Promise<boolean> {
    if (this.endFlight) return this.endFlight;
    if (!this.id) return Promise.resolve(false);
    this.ending = true; this.previous = null;
    this.endFlight = (async () => {
      if (this.flight) await this.flight;
      if (this.pendingCheckpoint && !this.stopped) await this.checkpoint();
      if (this.pendingCheckpoint && !this.stopped) return false;
      // A definitive lease/capability rejection can still reconcile/close, without credit.
      this.pendingEnd ??= JSON.stringify(this.stopped ? {} : { final_seq: this.seq, final_position_ms: Math.floor(this.latest.positionMs), final_duration_ms: Math.floor(this.latest.durationMs), final_playback_rate: this.latest.rate, final_client_cumulative_active_ms: Math.floor(this.total), final_client_epoch: this.epoch });
      try {
        const res = await this.request(`/playbacks/${this.id}/end`, { method: 'POST', body: this.pendingEnd });
        if (!res.ok) return false;
        this.stopped = true; return true;
      } catch { return false; }
    })().finally(() => { this.endFlight = null; });
    return this.endFlight;
  }
}
