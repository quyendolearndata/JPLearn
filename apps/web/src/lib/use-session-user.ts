"use client";

import { useEffect, useMemo, useState } from "react";
import {
  getToken,
  getUser,
  refreshUser,
  subscribeAuth,
  type StoredUser,
} from "./auth-storage";

export function useSessionUser() {
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState<StoredUser | null>(null);
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    const sync = (nextUser: StoredUser | null) => {
      setUser(nextUser);
      setToken(nextUser ? getToken() : null);
      setReady(true);
    };

    sync(getUser());
    void refreshUser().then(sync);
    return subscribeAuth(sync);
  }, []);

  const isStaff = useMemo(
    () => Boolean(user?.roles.includes("teacher") || user?.roles.includes("admin")),
    [user],
  );

  return { ready, user, token, isStaff };
}
