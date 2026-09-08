"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useFlags } from "../lib/flags";
import { getUser, refreshUser, subscribeAuth, type StoredUser } from "../lib/auth-storage";

export function Chrome({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
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
      <a className="skip-link" href="#main-content">Đến nội dung chính</a>
      <header className="app-header">
        <div className="nav-container">
          <Link href="/" className="nav-logo">
            <span className="logo-badge">j.</span>
            <span className="logo-title">JPLearn</span>
          </Link>
          <nav className="nav-main">
            <Link href="/catalog" aria-current={pathname === "/catalog" ? "page" : undefined}>Catalog</Link>
            <Link href="/session" aria-current={pathname === "/session" ? "page" : undefined}>Phiên</Link>
            <Link href="/progress" aria-current={pathname === "/progress" ? "page" : undefined}>Tiến độ</Link>
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
          <div className="sidebar-note"><span aria-hidden="true">❧</span><p>Mỗi ngày một chút.<br/>Tiếng Nhật gần hơn.</p></div>
        </div>
      </header>
      <main className="app-main" id="main-content"><div className="page-topline">Tiếng Nhật, theo nhịp của bạn.</div>{children}<footer className="app-footer">JPLearn · Hiểu từ những điều gần gũi.</footer></main>
    </>
  );
}
