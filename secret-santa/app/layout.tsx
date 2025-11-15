import type { Metadata } from "next";
import "./globals.css";
import Snowfall from "@/components/Snowfall";
import FallingTrees from "@/components/FallingTrees";

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
        <FallingTrees />
        <Snowfall />
        {children}
      </body>
    </html>
  );
}
