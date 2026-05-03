import type { Metadata } from "next";
import { Fraunces, Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  axes: ["SOFT", "WONK", "opsz"],
  display: "swap",
});

const geist = Geist({
  subsets: ["latin"],
  variable: "--font-geist",
  display: "swap",
});

const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-geist-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "egynaecologist · front desk",
  description: "Booking ledger for the front-desk team.",
  robots: { index: false, follow: false },
  // Don't override icons — Next.js auto-generates them from app/icon.png + app/icon.svg.
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-GB" className={`${fraunces.variable} ${geist.variable} ${geistMono.variable}`}>
      <body className="bg-paper text-ink antialiased min-h-screen">{children}</body>
    </html>
  );
}
