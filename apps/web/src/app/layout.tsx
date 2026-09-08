import type { Metadata } from "next";
import { Plus_Jakarta_Sans, Noto_Sans_JP } from "next/font/google";
import { FlagsProvider } from "../lib/flags";
import { Chrome } from "../components/chrome";
import "./globals.css";

const plusJakartaSans = Plus_Jakarta_Sans({
  subsets: ["latin", "vietnamese"],
  variable: "--font-sans-en",
  display: "swap",
});

const notoSansJP = Noto_Sans_JP({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-sans-jp",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "JPLearn — Catalog",
    template: "JPLearn — %s",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi" className={`${plusJakartaSans.variable} ${notoSansJP.variable}`}>
      <body>
        <FlagsProvider>
          <Chrome>{children}</Chrome>
        </FlagsProvider>
      </body>
    </html>
  );
}
