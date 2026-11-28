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
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#090D16] text-[#F8FAFC]">
        {children}
      </body>
    </html>
  );
}
