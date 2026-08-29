import { notFound } from "next/navigation";

import { ControlledCanvas } from "@/features/canvas/controlled-canvas";
import { hasLocale } from "@/i18n/messages";

export default async function Home({ params }: PageProps<"/[locale]">) {
  const { locale } = await params;
  if (!hasLocale(locale)) notFound();

  return <ControlledCanvas locale={locale} />;
}
