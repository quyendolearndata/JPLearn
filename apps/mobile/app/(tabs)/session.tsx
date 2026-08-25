import { useState } from "react";
import { Button, Text, View } from "react-native";
import { Platform, useWindowDimensions } from "react-native";
import * as SecureStore from "expo-secure-store";
import { useVideoPlayer, VideoView } from "expo-video";
import { tokens } from "@jplearn/design-tokens";
import type { CatalogItemPublic } from "@jplearn/domain";
import { api } from "../../src/api";
import { deviceClassFrom } from "../../src/deviceClass";
import { pickClipSource } from "../../src/pickClipSource";

export default function SessionScreen() {
  const { width, height } = useWindowDimensions();
  const deviceClass = deviceClassFrom({ os: Platform.OS, width, height });
  const padding = deviceClass === "ipad" ? tokens.spaceIpad : tokens.spacePhone;
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [clipSource, setClipSource] = useState<string | null>(null);
  const player = useVideoPlayer(clipSource, (p) => {
    p.loop = false;
  });

  async function start() {
    const token = await SecureStore.getItemAsync("access_token");
    if (!token) {
      setStatus("Hãy đăng nhập.");
      return;
    }
    const res = await api("/sessions", {
      method: "POST",
      token,
      body: JSON.stringify({ device_class: deviceClass }),
    });
    const body = await res.json();
    setSessionId(body.id);
    setStatus("Phiên đang chạy.");

    const catalogRes = await api("/catalog", { token });
    const catalog = (await catalogRes.json()) as { items: CatalogItemPublic[] };
    setClipSource(pickClipSource(catalog.items ?? []));
  }

  async function end() {
    const token = await SecureStore.getItemAsync("access_token");
    if (!token || !sessionId) return;
    await api(`/sessions/${sessionId}/end`, { method: "POST", token });
    setSessionId(null);
    setClipSource(null);
    setStatus("Đã kết thúc phiên.");
  }

  return (
    <View style={{ padding, gap: 8, flex: 1 }}>
      <Text>{status}</Text>
      {clipSource ? (
        <VideoView
          player={player}
          nativeControls
          style={{
            width: "100%",
            maxWidth: deviceClass === "ipad" ? 1024 : undefined,
            aspectRatio: 16 / 9,
            alignSelf: "center",
            flexGrow: deviceClass === "ipad" ? 1 : 0,
          }}
        />
      ) : null}
      <Button title="Bắt đầu phiên" onPress={() => void start()} />
      <Button title="Kết thúc phiên" onPress={() => void end()} />
    </View>
  );
}
