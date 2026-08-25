import { useState } from "react";
import { Button, Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import * as SecureStore from "expo-secure-store";
import { api } from "../src/api";

export default function LoginScreen() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("password10");

  async function submit(path: "/auth/register" | "/auth/login") {
    const res = await api(path, {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    const body = await res.json();
    await SecureStore.setItemAsync("access_token", body.access_token);
    router.replace("/(tabs)/catalog");
  }

  return (
    <View style={{ padding: 16, gap: 8 }}>
      <Text>Email</Text>
      <TextInput
        accessibilityLabel="Email"
        autoCapitalize="none"
        value={email}
        onChangeText={setEmail}
        style={{ borderWidth: 1, padding: 8 }}
      />
      <Text>Mật khẩu</Text>
      <TextInput
        accessibilityLabel="Mật khẩu"
        secureTextEntry
        value={password}
        onChangeText={setPassword}
        style={{ borderWidth: 1, padding: 8 }}
      />
      <Button title="Đăng nhập" onPress={() => void submit("/auth/login")} />
      <Button title="Đăng ký" onPress={() => void submit("/auth/register")} />
    </View>
  );
}
