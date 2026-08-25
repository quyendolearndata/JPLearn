import { useEffect, useState } from "react";
import { Text, View, useWindowDimensions } from "react-native";
import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";
import { tokens } from "@jplearn/design-tokens";
import type { LearnerProgress } from "@jplearn/domain";
import { api } from "../../src/api";
import { deviceClassFrom } from "../../src/deviceClass";

export default function ProgressScreen() {
  const { width, height } = useWindowDimensions();
  const device = deviceClassFrom({ os: Platform.OS, width, height });
  const padding = device === "ipad" ? tokens.spaceIpad : tokens.spacePhone;
  const [progress, setProgress] = useState<LearnerProgress | null>(null);

  useEffect(() => {
    void (async () => {
      const token = await SecureStore.getItemAsync("access_token");
      if (!token) return;
      const res = await api("/progress", { token });
      setProgress((await res.json()) as LearnerProgress);
    })();
  }, []);

  return (
    <View style={{ padding }}>
      {progress ? (
        <Text>
          {progress.minutes_comprehensible} phút · cấp {progress.current_ci_level}
        </Text>
      ) : (
        <Text>Hãy đăng nhập.</Text>
      )}
    </View>
  );
}
