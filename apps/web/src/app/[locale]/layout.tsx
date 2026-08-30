import type { Metadata } from "next";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { hasLocale } from "@/i18n/messages";

export const metadata: Metadata = {
  title: "Interactive Taste Learning",
  description: "A workspace for refining interface preferences.",
};

export default async function LocaleLayout({
  children,
  params,
}: Readonly<{ children: ReactNode; params: Promise<{ locale: string }> }>) {
  const { locale } = await params;
  if (!hasLocale(locale)) notFound();

  return (
    <html lang={locale}>
      <body>{children}</body>
    </html>
  );
}
