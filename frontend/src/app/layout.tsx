import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Airlock Reviewer Dashboard",
  description: "Security gateway reviewer dashboard for Airlock AI agent sessions",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[#F4F5F7] text-[#191A1C]">
        {children}
      </body>
    </html>
  );
}
