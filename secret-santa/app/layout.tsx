import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Secret Santa - Gift Exchange Manager",
  description: "Manage your Secret Santa gift exchange with wishlists and assignments",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
