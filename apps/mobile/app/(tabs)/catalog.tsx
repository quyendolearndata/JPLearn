import { useEffect, useState } from "react";
import { FlatList, Text, useWindowDimensions, View } from "react-native";
import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";
import { tokens } from "@jplearn/design-tokens";
import type { CatalogItemPublic } from "@jplearn/domain";
import { api } from "../../src/api";
import { deviceClassFrom } from "../../src/deviceClass";

export default function CatalogScreen() {
  const { width, height } = useWindowDimensions();
  const device = deviceClassFrom({ os: Platform.OS, width, height });
  const padding = device === "ipad" ? tokens.spaceIpad : tokens.spacePhone;
  const numColumns = device === "ipad" ? 2 : 1;
  const [items, setItems] = useState<CatalogItemPublic[]>([]);

  useEffect(() => {
    void (async () => {
      const token = await SecureStore.getItemAsync("access_token");
      if (!token) return;
      const res = await api("/catalog", { token });
      const body = (await res.json()) as { items: CatalogItemPublic[] };
      setItems(body.items ?? []);
    })();
  }, []);

  return (
    <View style={{ padding }}>
      <FlatList
        data={items}
        key={numColumns}
        numColumns={numColumns}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <Text style={{ flex: 1, padding: 8 }}>
            {item.topic_id} · cấp {item.ci_level}
          </Text>
        )}
      />
    </View>
  );
}
