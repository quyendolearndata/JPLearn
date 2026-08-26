import type { Metadata } from "next";
import { FlagsProvider } from "../lib/flags";
import { Chrome } from "../components/chrome";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "JPLearn — Catalog",
    template: "JPLearn — %s",
  },
};

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
