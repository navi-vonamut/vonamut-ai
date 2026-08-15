import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VONAMUT AI | Bybit Autonomous Trading Terminal",
  description: "Next.js 16 High-Density Monochrome Trading Terminal with LangGraph & Gemini/Gemma Intelligence",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-background text-foreground antialiased min-h-screen selection:bg-zinc-800 selection:text-white">
        {children}
      </body>
    </html>
  );
}
