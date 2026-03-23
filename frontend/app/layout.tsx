import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Stock Watchlist",
  description: "Live watchlist and top-mover dashboard for the stocks serverless pipeline.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
