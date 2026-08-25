import { useState } from "react";
import { Button, Text, View } from "react-native";
import { Platform, useWindowDimensions } from "react-native";
import * as SecureStore from "expo-secure-store";
import { tokens } from "@jplearn/design-tokens";
import { api } from "../../src/api";
import { deviceClassFrom } from "../../src/deviceClass";

export default function SessionScreen() {
  const { width, height } = useWindowDimensions();
  const deviceClass = deviceClassFrom({ os: Platform.OS, width, height });
  const padding = deviceClass === "ipad" ? tokens.spaceIpad : tokens.spacePhone;
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState("");

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
  }

  async function end() {
    const token = await SecureStore.getItemAsync("access_token");
    if (!token || !sessionId) return;
    await api(`/sessions/${sessionId}/end`, { method: "POST", token });
    setSessionId(null);
    setStatus("Đã kết thúc phiên.");
  }

  return (
    <View style={{ padding, gap: 8 }}>
      <Text>{status}</Text>
      <Button title="Bắt đầu phiên" onPress={() => void start()} />
      <Button title="Kết thúc phiên" onPress={() => void end()} />
    </View>
  );
}
