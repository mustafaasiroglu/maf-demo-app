import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Yatırım Botu - Akıllı Yatırım Danışmanınız",
  description: "Akıllı yatırım danışmanınız",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="tr">
      <body>{children}</body>
    </html>
  );
}
