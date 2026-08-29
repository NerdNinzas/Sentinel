import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "Sentinel — AI Incident Commander", description: "The intelligence layer inside the incident room. Built on Agora Conversational AI." };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen antialiased" style={{ fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif" }}>{children}</body>
    </html>
  );
}
