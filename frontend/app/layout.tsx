import "./globals.css";

import { NavBar } from "@/components/nav-bar";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <NavBar />
        <main className="container">{children}</main>
      </body>
    </html>
  );
}
