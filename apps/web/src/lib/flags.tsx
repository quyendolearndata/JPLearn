"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import type { Flags } from "@jplearn/domain";
import { DEFAULT_FLAGS } from "@jplearn/domain";
import { api } from "./api";
import { getToken, subscribeAuth } from "./auth-storage";

const FlagsContext = createContext<Flags>(DEFAULT_FLAGS);

export function FlagsProvider({ children }: { children: ReactNode }) {
  const [flags, setFlags] = useState<Flags>(DEFAULT_FLAGS);

  useEffect(() => {
    let cancelled = false;

    async function loadFlags() {
      const token = getToken();
      if (!token) {
        if (!cancelled) setFlags(DEFAULT_FLAGS);
        return;
      }
      try {
        const res = await api("/flags", { token });
        if (cancelled) return;
        if (res.ok) {
          const data = (await res.json()) as Flags;
          if (!cancelled) setFlags(data);
        } else {
          if (!cancelled) setFlags(DEFAULT_FLAGS);
        }
      } catch {
        if (!cancelled) setFlags(DEFAULT_FLAGS);
      }
    }

    void loadFlags();
    const unsubscribe = subscribeAuth(() => {
      void loadFlags();
    });

    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, []);

  return <FlagsContext.Provider value={flags}>{children}</FlagsContext.Provider>;
}

export function useFlags() {
  return useContext(FlagsContext);
}

