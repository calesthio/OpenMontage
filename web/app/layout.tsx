import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OpenMontage",
  description: "AI-orchestrated video production platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" className="dark h-full antialiased">
      <body className="min-h-full bg-background text-foreground flex flex-col font-sans">
        {children}
      </body>
    </html>
  );
}
