import { api } from "./api";

const TOKEN_KEY = "jplearn.access_token";
const USER_KEY = "jplearn.user";

export type StoredUser = {
  id: string;
  email: string;
  roles: string[];
};

type AuthListener = (user: StoredUser | null) => void;
const listeners = new Set<AuthListener>();

export function subscribeAuth(listener: AuthListener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function notifyListeners(user: StoredUser | null) {
  for (const fn of listeners) {
    try {
      fn(user);
    } catch {
      // ignore listener errors
    }
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser(): StoredUser | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredUser;
  } catch {
    return null;
  }
}

export function setSession(accessToken: string, user: StoredUser) {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, accessToken);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  notifyListeners(user);
}

export function clearSession() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  notifyListeners(null);
}

export async function logout(): Promise<{ serverRevoked: boolean; message: string }> {
  const token = getToken();
  let serverRevoked = false;

  if (token) {
    try {
      const res = await api("/auth/logout", {
        method: "POST",
        token,
      });
      serverRevoked = res.status === 204 || res.ok;
    } catch {
      serverRevoked = false;
    }
  }

  clearSession();

  if (serverRevoked) {
    return {
      serverRevoked: true,
      message: "Đã đăng xuất và thu hồi phiên trên mọi thiết bị.",
    };
  }

  return {
    serverRevoked: false,
    message: "Đã xóa phiên trên thiết bị này. Chưa xác nhận được thu hồi trên server do mất kết nối.",
  };
}

export async function refreshUser(): Promise<StoredUser | null> {
  const token = getToken();
  if (!token) {
    clearSession();
    return null;
  }
  try {
    const res = await api("/me", { token });
    if (res.status === 401) {
      clearSession();
      return null;
    }
    if (res.ok) {
      const user = (await res.json()) as StoredUser;
      if (typeof window !== "undefined") {
        localStorage.setItem(USER_KEY, JSON.stringify(user));
      }
      notifyListeners(user);
      return user;
    }
  } catch {
    // Network error: keep existing user in storage
  }
  return getUser();
}

export function hasRole(role: "learner" | "teacher" | "admin"): boolean {
  const user = getUser();
  return Boolean(user?.roles.includes(role));
}

