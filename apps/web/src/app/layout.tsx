"use client";

import Link from "next/link";
import { FlagsProvider } from "../lib/flags";
import "./globals.css";

function Chrome({ children }: { children: React.ReactNode }) {
  return (
    <>
      <nav>
        <Link href="/">Catalog</Link>
        <Link href="/session">Phiên</Link>
        <Link href="/progress">Tiến độ</Link>
        <Link href="/staff">Staff</Link>
        <Link href="/login">Tài khoản</Link>
      </nav>
      <main>{children}</main>
    </>
  );
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body>
        <FlagsProvider>
          <Chrome>{children}</Chrome>
        </FlagsProvider>
      </body>
    </html>
  );
}
