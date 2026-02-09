import type { Metadata } from "next";
import { Outfit, Noto_Serif_JP } from "next/font/google";
import "./globals.css";

const outfit = Outfit({
  variable: "--font-outfit",
  subsets: ["latin"],
});

const notoSerifJp = Noto_Serif_JP({
  variable: "--font-noto-serif-jp",
  weight: ["300", "600"],
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ZenFit - Harmonie & Mouvement",
  description: "Coach postural intelligent en Next.js",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fr">
      <body className={`${outfit.variable} ${notoSerifJp.variable} font-outfit antialiased`}>
        {children}
      </body>
    </html>
  );
}
