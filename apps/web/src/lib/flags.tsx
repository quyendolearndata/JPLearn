"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import type { Flags } from "@jplearn/domain";
import { DEFAULT_FLAGS } from "@jplearn/domain";
import { api } from "./api";
import { getToken } from "./auth-storage";

const FlagsContext = createContext<Flags>(DEFAULT_FLAGS);

export function FlagsProvider({ children }: { children: ReactNode }) {
  const [flags, setFlags] = useState<Flags>(DEFAULT_FLAGS);
  useEffect(() => {
    const token = getToken();
    if (!token) return;
    void api("/flags", { token })
      .then((res) => (res.ok ? res.json() : DEFAULT_FLAGS))
      .then((data: Flags) => setFlags(data));
  }, []);
  return <FlagsContext.Provider value={flags}>{children}</FlagsContext.Provider>;
}

export function useFlags() {
  return useContext(FlagsContext);
}
