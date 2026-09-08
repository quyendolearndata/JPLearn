import type { Metadata } from "next";

export const metadata: Metadata = { title: "Catalog" };

export default function CatalogLayout({ children }: { children: React.ReactNode }) {
  return children;
}
