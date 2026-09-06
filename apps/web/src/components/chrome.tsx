"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useFlags } from "../lib/flags";
import { getUser, refreshUser, subscribeAuth, type StoredUser } from "../lib/auth-storage";

export function Chrome({ children }: { children: React.ReactNode }) {
  const flags = useFlags();
  const [user, setUser] = useState<StoredUser | null>(null);

  useEffect(() => {
    setUser(getUser());
    void refreshUser().then((u) => setUser(u));

    const unsubscribe = subscribeAuth((updatedUser) => {
      setUser(updatedUser);
    });

    return () => {
      unsubscribe();
    };
  }, []);

  const isStaff = Boolean(
    user?.roles?.includes("teacher") || user?.roles?.includes("admin"),
  );

  return (
    <>
      <header className="app-header">
        <div className="nav-container">
          <Link href="/" className="nav-logo">
            <span className="logo-badge">JP</span>
            <span className="logo-title">JPLearn</span>
          </Link>
          <nav className="nav-main">
            <Link href="/catalog">Catalog</Link>
            <Link href="/session">Phiên</Link>
            <Link href="/progress">Tiến độ</Link>
            {isStaff ? <Link href="/staff" className="nav-staff-link">Staff</Link> : null}
            <Link href="/login" className="nav-auth-link">
              {user ? (
                <span className="user-badge" title={user.email}>
                  {user.email.split("@")[0]}
                </span>
              ) : (
                "Tài khoản"
              )}
            </Link>
            {flags.grammar_enabled ? <Link href="/grammar">Ngữ pháp</Link> : null}
            {flags.flashcards_enabled ? <Link href="/flashcards">Flashcard</Link> : null}
            {flags.l1_subtitles_enabled ? <span>Bản dịch</span> : null}
            {flags.speaking_enabled ? <Link href="/speak">Nói</Link> : null}
          </nav>
        </div>
      </header>
      <main className="app-main">{children}</main>
    </>
  );
}

