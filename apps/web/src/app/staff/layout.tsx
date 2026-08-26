import type { Metadata } from "next";

export const metadata: Metadata = { title: "Staff CMS" };

export default function StaffLayout({ children }: { children: React.ReactNode }) {
  return children;
}
