"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, parseApiError } from "../../lib/api";
import { getUser, logout, setSession, subscribeAuth, type StoredUser } from "../../lib/auth-storage";
import { getSafeRedirect } from "../../lib/safe-redirect";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [currentUser, setCurrentUser] = useState<StoredUser | null>(null);

  useEffect(() => {
    setCurrentUser(getUser());
    const unsubscribe = subscribeAuth((user) => {
      setCurrentUser(user);
    });
    return () => unsubscribe();
  }, []);

  function validateInput(): boolean {
    if (!email || !email.includes("@")) {
      setError("Vui lòng nhập địa chỉ email hợp lệ.");
      return false;
    }
    if (!password || password.length < 10) {
      setError("Mật khẩu phải có độ dài ít nhất 10 ký tự.");
      return false;
    }
    return true;
  }

  async function submit(path: "/auth/register" | "/auth/login") {
    setError("");
    setNotice("");

    if (!validateInput()) {
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await api(path, {
        method: "POST",
        body: JSON.stringify({ email: email.trim(), password }),
      });

      if (!res.ok) {
        const err = await parseApiError(res);
        if (res.status === 400) {
          setError(err.message || "Yêu cầu không hợp lệ.");
        } else if (res.status === 401) {
          setError("Email hoặc mật khẩu không chính xác.");
        } else if (res.status === 409) {
          setError("Email này đã được đăng ký. Vui lòng đăng nhập.");
        } else if (res.status === 422) {
          setError(err.message || "Dữ liệu không hợp lệ. Mật khẩu cần ít nhất 10 ký tự.");
        } else {
          setError(err.message || "Không thể xử lý yêu cầu.");
        }
        return;
      }

      const body = await res.json();
      setSession(body.access_token, body.user);

      // Check redirect param with safe sanitization (R-07)
      const params = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : null;
      const redirectTarget = getSafeRedirect(params?.get("redirect") ?? null);
      router.push(redirectTarget);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Lỗi kết nối máy chủ";
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleLogout() {
    setIsSubmitting(true);
    setError("");
    try {
      const result = await logout();
      setNotice(result.message);
    } catch {
      setError("Có lỗi xảy ra khi đăng xuất.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="login-card">
      <h1>Tài khoản</h1>

      {currentUser ? (
        <div className="logged-in-panel">
          <p>
            Đang đăng nhập: <strong>{currentUser.email}</strong>
          </p>
          <p className="roles-info">
            Vai trò: {currentUser.roles?.join(", ") || "learner"}
          </p>
          <p className="logout-note">
            (Đăng xuất sẽ thu hồi phiên trên toàn bộ thiết bị đã đăng nhập)
          </p>
          <button
            type="button"
            className="btn-danger"
            disabled={isSubmitting}
            onClick={() => void handleLogout()}
          >
            {isSubmitting ? "Đang xử lý…" : "Đăng xuất"}
          </button>
        </div>
      ) : null}

      {notice ? <p className="status-notice">{notice}</p> : null}
      {error ? <p className="status-error" role="alert">{error}</p> : null}

      <div className="form-group">
        <label htmlFor="email">Email</label>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="username"
          placeholder="learner@example.com"
          value={email}
          disabled={isSubmitting}
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>

      <div className="form-group">
        <label htmlFor="password">Mật khẩu</label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          placeholder="Ít nhất 10 ký tự"
          value={password}
          disabled={isSubmitting}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>

      <div className="button-group">
        <button
          type="button"
          disabled={isSubmitting}
          onClick={() => void submit("/auth/login")}
        >
          {isSubmitting ? "Đang xử lý…" : "Đăng nhập"}
        </button>
        <button
          type="button"
          disabled={isSubmitting}
          onClick={() => void submit("/auth/register")}
        >
          {isSubmitting ? "Đang xử lý…" : "Đăng ký"}
        </button>
      </div>
    </section>
  );
}

