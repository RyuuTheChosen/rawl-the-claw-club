import type { Metadata, Viewport } from "next";
import { Inter, Press_Start_2P, JetBrains_Mono } from "next/font/google";
import { headers } from "next/headers";
import "./globals.css";
import { Providers } from "@/components/Providers";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { CrtOverlay } from "@/components/CrtOverlay";
import { Toaster } from "sonner";

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
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "https://rawl.gg"),
  title: {
    default: "Rawl - AI Fighting Game Arena",
    template: "%s | Rawl",
  },
  description: "Train AI fighters, compete in ranked matches, and bet ETH on outcomes — all on-chain.",
  openGraph: {
    title: "Rawl - AI Fighting Game Arena",
    description: "Train AI fighters, compete in ranked matches, and bet ETH on outcomes — all on-chain.",
    url: "https://rawl.gg",
    siteName: "Rawl",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "Rawl - AI Fighting Game Arena" }],
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Rawl - AI Fighting Game Arena",
    description: "Train AI fighters, compete in ranked matches, and bet ETH on outcomes.",
    images: ["/og-image.png"],
  },
  icons: { icon: "/favicon.svg" },
};

export const viewport: Viewport = {
  themeColor: "#FF4500",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const cookie = (await headers()).get('cookie') ?? undefined;
  return (
    <html
      lang="en"
      className={`dark ${inter.variable} ${pixelFont.variable} ${mono.variable}`}
    >
      <body className="min-h-screen">
        <Providers cookie={cookie}>
          <Navbar />
          <main>{children}</main>
          <Footer />
        </Providers>
        <CrtOverlay />
        <Toaster theme="dark" />
      </body>
    </html>
  );
}
