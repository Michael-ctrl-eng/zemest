import type { Metadata } from "next";
import { Inter, Instrument_Serif, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";
import { ToastContainer } from "@/components/site/toast";

const inter = Inter({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800", "900"],
});

const instrumentSerif = Instrument_Serif({
  variable: "--font-serif-display",
  subsets: ["latin"],
  weight: ["400"],
  style: ["normal", "italic"],
});

const jetbrains = JetBrains_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  weight: ["400", "500", "700"],
});

export const metadata: Metadata = {
  title: "Zemest — AI Moderation Agents",
  description:
    "Ready-made AI moderation agents for WhatsApp, Facebook, and Instagram. Rabbit v1 speaks Arabic with every accent. Rooster v1 speaks English with every accent. Understands voice, images, and text.",
  keywords: [
    "Zemest",
    "AI moderation",
    "WhatsApp agent",
    "Facebook agent",
    "Instagram agent",
    "Rabbit v1",
    "Rooster v1",
    "Arabic AI",
    "English AI",
    "conversational commerce",
    "AI agent",
    "inventory agent",
  ],
  authors: [{ name: "Zemest" }],
  icons: {
    icon: "/zemest-logo.png",
  },
  openGraph: {
    title: "Zemest — AI Moderation Agents",
    description:
      "Ready-made AI moderation agents for WhatsApp, Facebook, and Instagram. Rabbit v1 (Arabic) + Rooster v1 (English).",
    siteName: "Zemest",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Zemest — AI Moderation Agents",
    description:
      "Ready-made AI moderation agents for WhatsApp, Facebook, and Instagram. Rabbit v1 (Arabic) + Rooster v1 (English).",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning data-scroll-behavior="smooth">
      <body
        className={`${inter.variable} ${instrumentSerif.variable} ${jetbrains.variable} antialiased bg-background text-foreground`}
      >
        {children}
        <Toaster />
        <ToastContainer />
      </body>
    </html>
  );
}
