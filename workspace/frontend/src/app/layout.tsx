import type { Metadata } from "next";
import { Plus_Jakarta_Sans, Space_Grotesk, Noto_Sans_JP } from "next/font/google";
import "../styles/globals.css";

const jakarta = Plus_Jakarta_Sans({
  variable: "--font-body",
  subsets: ["latin"],
});

const spaceGrotesk = Space_Grotesk({
  variable: "--font-display",
  subsets: ["latin"],
});

const notoJP = Noto_Sans_JP({
  variable: "--font-zen",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ZenFit - Harmonie & Mouvement",
  description: "Live coaching with RTMW3D pose, avatar, and debug tools.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${jakarta.variable} ${spaceGrotesk.variable} ${notoJP.variable} antialiased`}>
        <div className="app-shell">
          {children}
        </div>
      </body>
    </html>
  );
}
