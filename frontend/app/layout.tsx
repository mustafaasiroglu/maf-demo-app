import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Yatırım Botu - Garanti",
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
