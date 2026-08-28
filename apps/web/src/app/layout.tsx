import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Interactive Taste Learning",
  description: "A blank shell for Interactive Taste Learning.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
