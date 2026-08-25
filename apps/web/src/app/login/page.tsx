"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "../../lib/api";
import { setSession } from "../../lib/auth-storage";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("password10");
  const [error, setError] = useState("");

  async function submit(path: "/auth/register" | "/auth/login") {
    setError("");
    const res = await api(path, {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      setError("Không đăng nhập được");
      return;
    }
    const body = await res.json();
    setSession(body.access_token, body.user);
    router.push("/");
  }

  return (
    <section>
      <h1>Tài khoản</h1>
      <label htmlFor="email">Email</label>
      <input
        id="email"
        name="email"
        type="email"
        autoComplete="username"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      <label htmlFor="password">Mật khẩu</label>
      <input
        id="password"
        name="password"
        type="password"
        autoComplete="current-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      {error ? <p>{error}</p> : null}
      <button type="button" onClick={() => void submit("/auth/login")}>
        Đăng nhập
      </button>
      <button type="button" onClick={() => void submit("/auth/register")}>
        Đăng ký
      </button>
    </section>
  );
}
