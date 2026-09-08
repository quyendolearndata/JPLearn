"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  ["/staff", "Nội dung"],
  ["/staff/series", "Series"],
  ["/staff/reports", "Báo lỗi"],
  ["/staff/jobs", "AI Jobs"],
  ["/staff/ai-usage", "AI Usage"],
] as const;

export function StaffNav() {
  const pathname = usePathname();
  return (
    <nav className="subnav" aria-label="Điều hướng quản trị">
      {LINKS.map(([href, label]) => (
        <Link
          key={href}
          href={href}
          aria-current={pathname === href || (href !== "/staff" && pathname.startsWith(`${href}/`)) ? "page" : undefined}
        >
          {label}
        </Link>
      ))}
    </nav>
  );
}
