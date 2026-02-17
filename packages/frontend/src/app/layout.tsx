import type { Metadata } from "next";
import { Inter, Press_Start_2P, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { WalletProvider } from "@/components/WalletProvider";
import { Navbar } from "@/components/Navbar";
import { CrtOverlay } from "@/components/CrtOverlay";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

const pixelFont = Press_Start_2P({
  weight: "400",
  subsets: ["latin"],
  variable: "--font-pixel",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "Rawl - AI Fighting Game Arena",
  description: "Watch AI fighters battle, train your own, and bet on matches",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`dark ${inter.variable} ${pixelFont.variable} ${mono.variable}`}
    >
      <body className="min-h-screen">
        <WalletProvider>
          <Navbar />
          <main>{children}</main>
        </WalletProvider>
        <CrtOverlay />
      </body>
    </html>
  );
}
