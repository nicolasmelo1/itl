import { notFound } from "next/navigation";

import { ControlledCanvas } from "@/features/canvas/controlled-canvas";
import { hasLocale } from "@/i18n/messages";

type HomeProps = {
  params: Promise<{ locale: string }>;
};

export default async function Home({ params }: HomeProps) {
  const { locale } = await params;
  if (!hasLocale(locale)) notFound();

  return <ControlledCanvas locale={locale} />;
}
