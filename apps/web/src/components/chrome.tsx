"use client";

import Link from "next/link";
import { useFlags } from "../lib/flags";

export function Chrome({ children }: { children: React.ReactNode }) {
  const flags = useFlags();
  return (
    <>
      <nav>
        <Link href="/">Catalog</Link>
        <Link href="/session">Phiên</Link>
        <Link href="/progress">Tiến độ</Link>
        <Link href="/staff">Staff</Link>
        <Link href="/login">Tài khoản</Link>
        {flags.grammar_enabled ? <Link href="/grammar">Ngữ pháp</Link> : null}
        {flags.flashcards_enabled ? <Link href="/flashcards">Flashcard</Link> : null}
        {flags.l1_subtitles_enabled ? <span>Bản dịch</span> : null}
        {flags.speaking_enabled ? <Link href="/speak">Nói</Link> : null}
      </nav>
      <main>{children}</main>
    </>
  );
}
