import { NextResponse, type NextRequest } from "next/server";

function preferredLocale(request: NextRequest): "en" | "pt-BR" {
  const acceptedLanguages = request.headers.get("accept-language")?.toLowerCase() ?? "";
  return acceptedLanguages.startsWith("pt") || acceptedLanguages.includes(",pt") ? "pt-BR" : "en";
}

export function proxy(request: NextRequest) {
  const response = NextResponse.redirect(new URL(`/${preferredLocale(request)}`, request.url));
  response.headers.set("Vary", "Accept-Language");
  return response;
}

export const config = { matcher: "/" };
