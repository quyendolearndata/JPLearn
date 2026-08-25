import { useEffect, useState } from "react";
import { Text, View } from "react-native";
import * as SecureStore from "expo-secure-store";
import type { LearnerProgress } from "@jplearn/domain";
import { api } from "../../src/api";

export default function ProgressScreen() {
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
    <View style={{ padding: 16 }}>
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
