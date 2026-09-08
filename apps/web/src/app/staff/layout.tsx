import type { Metadata } from "next";
import { StaffNav } from "../../components/staff-nav";

export const metadata: Metadata = { title: "Staff CMS" };

export default function StaffLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <StaffNav />
      {children}
    </>
  );
}
