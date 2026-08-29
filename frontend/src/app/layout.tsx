import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "Sentinel — AI Incident Commander", description: "The intelligence layer inside the incident room" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased font-[system-ui]">{children}</body>
    </html>
  );
}
