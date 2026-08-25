import { Tabs } from "expo-router";

export default function TabsLayout() {
  return (
    <Tabs>
      <Tabs.Screen name="catalog" options={{ title: "Catalog" }} />
      <Tabs.Screen name="session" options={{ title: "Phiên" }} />
      <Tabs.Screen name="progress" options={{ title: "Tiến độ" }} />
    </Tabs>
  );
}
