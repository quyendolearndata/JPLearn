import type { Metadata } from "next";

export const metadata: Metadata = { title: "Phiên học" };

export default function SessionLayout({ children }: { children: React.ReactNode }) {
  return children;
}
