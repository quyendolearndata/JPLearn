import { useEffect, useRef, useState } from "react";
import { AppState, Button, Text, View, Platform, useWindowDimensions } from "react-native";
import * as SecureStore from "expo-secure-store";
import { useVideoPlayer, VideoView } from "expo-video";
import { tokens } from "@jplearn/design-tokens";
import type { CatalogItemPublic } from "@jplearn/domain";
import { api } from "../../src/api";
import { deviceClassFrom } from "../../src/deviceClass";
import { MobilePlaybackTracker } from "../../src/playbackTracker";

const uniqueId = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;

export default function SessionScreen() {
  const { width, height } = useWindowDimensions();
  const deviceClass = deviceClassFrom({ os: Platform.OS, width, height });
  const padding = deviceClass === "ipad" ? tokens.spaceIpad : tokens.spacePhone;
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [started, setStarted] = useState(false);
  const [clipSource, setClipSource] = useState<string | null>(null);
  const tracker = useRef<MobilePlaybackTracker | null>(null);
  const pending = useRef<{ item: CatalogItemPublic; version: string } | null>(null);
  const legacyKey = useRef<string | null>(null);
  const foreground = useRef(AppState.currentState === "active");
  const resumeMs = useRef<number | null>(null);
  const player = useVideoPlayer(clipSource, (p) => { p.loop = false; p.timeUpdateEventInterval = 0.5; });

  useEffect(() => {
    const sample = () => tracker.current?.sample({ positionMs: player.currentTime * 1000, durationMs: (Number.isFinite(player.duration) ? player.duration : 0) * 1000, rate: player.playbackRate, playing: player.playing, ready: player.status === "readyToPlay", foreground: foreground.current });
    const subscriptions = [
      player.addListener("timeUpdate", sample),
      player.addListener("playingChange", ({ isPlaying }) => { sample(); if (!isPlaying) void tracker.current?.checkpoint(); }),
      player.addListener("statusChange", sample),
      player.addListener("sourceLoad", () => { if (resumeMs.current !== null) { player.currentTime = resumeMs.current / 1000; resumeMs.current = null; } sample(); }),
      player.addListener("playToEnd", () => { sample(); void tracker.current?.end(); }),
    ];
    const appState = AppState.addEventListener("change", (state) => {
      foreground.current = state === "active";
      if (!foreground.current) { sample(); player.pause(); void tracker.current?.checkpoint(); }
    });
    const timer = setInterval(() => { sample(); if (foreground.current) void tracker.current?.checkpoint(); }, 15000);
    return () => { subscriptions.forEach((s) => s.remove()); appState.remove(); clearInterval(timer); void tracker.current?.end(); };
  }, [player]);

  async function start() {
    if (busy || started) return;
    setBusy(true);
    try {
      const token = await SecureStore.getItemAsync("access_token");
      if (!token) { setStatus("Hãy đăng nhập."); return; }
      if (!pending.current) {
        const catalogRes = await api("/catalog", { token });
        if (!catalogRes.ok) throw new Error("Không tải được danh mục.");
        const catalog = await catalogRes.json() as { items: CatalogItemPublic[] };
        const item = catalog.items.find((entry) => entry.hls_url || entry.playback_url);
        if (!item) throw new Error("Chưa có video để phát.");
        const capsRes = await api("/capabilities", { token });
        if (!capsRes.ok) throw new Error("Không kiểm tra được tính năng. Hãy thử lại.");
        const caps = await capsRes.json();
        if (caps.playback_tracking_enabled) {
          const contentRes = await api(`/catalog/${item.id}/content`, { token });
          if (!contentRes.ok) throw new Error("Chưa tải được phiên bản video. Hãy thử lại.");
          const content = await contentRes.json();
          if (!content.id) throw new Error("Video chưa có phiên bản đã duyệt.");
          pending.current = { item, version: content.id };
          tracker.current = new MobilePlaybackTracker((path, init) => api(path, { ...init, token }), () => performance.now(), uniqueId, () => { player.pause(); setStatus("Ghi nhận đã dừng. Kết thúc phiên rồi mở lại để tiếp tục."); });
        } else { pending.current = { item, version: "" }; }
      }
      const selected = pending.current;
      if (tracker.current) {
        const position = await tracker.current.start(selected.item.id, selected.version, deviceClass);
        if (position === null) { setStatus("Chưa xác nhận bắt đầu. Thử lại; nếu thiết bị khác đang phát, hãy kết thúc phiên tại đó."); return; }
        resumeMs.current = position;
      } else {
        legacyKey.current ??= uniqueId();
        const res = await api("/sessions", { method: "POST", token, headers: { "Idempotency-Key": legacyKey.current }, body: JSON.stringify({ device_class: deviceClass, catalog_item_id: selected.item.id }) });
        if (!res.ok) throw new Error("Chưa xác nhận bắt đầu. Hãy thử lại.");
        const body = await res.json(); setSessionId(body.id);
      }
      setClipSource(selected.item.hls_url ?? selected.item.playback_url ?? null);
      setStarted(true); setStatus("Phiên đã sẵn sàng. Bấm phát video.");
    } catch (error) { setStatus(error instanceof Error ? error.message : "Kết nối gián đoạn. Hãy thử lại."); }
    finally { setBusy(false); }
  }
  async function end() {
    if (busy) return;
    setBusy(true); player.pause();
    try {
      if (tracker.current) { if (!await tracker.current.end()) { setStatus("Chưa xác nhận kết thúc. Bấm Kết thúc phiên để thử lại."); return; } }
      else if (sessionId) {
        const token = await SecureStore.getItemAsync("access_token");
        if (!token) throw new Error("Hãy đăng nhập lại để kết thúc phiên.");
        const res = await api(`/sessions/${sessionId}/end`, { method: "POST", token });
        if (!res.ok) throw new Error("Chưa xác nhận kết thúc. Hãy thử lại.");
      }
      tracker.current = null; pending.current = null; legacyKey.current = null;
      setSessionId(null); setStarted(false); setClipSource(null); setStatus("Đã kết thúc phiên.");
    } catch (error) { setStatus(error instanceof Error ? error.message : "Kết nối gián đoạn. Hãy thử lại."); }
    finally { setBusy(false); }
  }
  return <View style={{ padding, gap: 8, flex: 1 }}>
    <Text accessibilityLiveRegion="polite">{status}</Text>
    {clipSource ? <VideoView player={player} nativeControls style={{ width: "100%", maxWidth: deviceClass === "ipad" ? 1024 : undefined, aspectRatio: 16 / 9, alignSelf: "center", flexGrow: deviceClass === "ipad" ? 1 : 0 }} /> : null}
    <Button title="Bắt đầu phiên" disabled={busy || started} onPress={() => void start()} />
    <Button title="Kết thúc phiên" disabled={busy || !started} onPress={() => void end()} />
  </View>;
}
