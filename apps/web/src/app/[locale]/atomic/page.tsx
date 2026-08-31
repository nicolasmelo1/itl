import { notFound } from "next/navigation";

import { AtomicSystemPreview } from "@/features/canvas/atomic-system-preview";
import { hasLocale } from "@/i18n/messages";

type AtomicPageProps = {
  params: Promise<{ locale: string }>;
};

export default async function AtomicPage({ params }: AtomicPageProps) {
  const { locale } = await params;
  if (!hasLocale(locale)) notFound();

  return <AtomicSystemPreview />;
}
