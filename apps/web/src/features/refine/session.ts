const STORAGE_KEY = "itl.taste.session-id";

/**
 * One acquisition session, one identifier.
 *
 * The first judgments this project collected were all recorded as `local`
 * because the client hardcoded it, which made session hold-out — the primary
 * benchmark — impossible after the fact. The API now refuses a placeholder, so
 * the client has to mean it.
 */
export function currentSessionId(): string {
  const stored = readStoredSessionId();
  if (stored) return stored;
  const created = newSessionId();
  storeSessionId(created);
  return created;
}

function newSessionId(): string {
  const day = new Date().toISOString().slice(0, 10);
  return `bench-${day}-${randomSuffix()}`;
}

function randomSuffix(): string {
  const uuid = globalThis.crypto?.randomUUID?.();
  return uuid ? uuid.slice(0, 8) : Math.random().toString(36).slice(2, 10).padEnd(8, "0");
}

function readStoredSessionId(): string | undefined {
  if (typeof window === "undefined") return undefined;
  try {
    return window.sessionStorage.getItem(STORAGE_KEY) ?? undefined;
  } catch {
    // A blocked storage partition must not stop a judgment being recorded; it
    // only costs this tab a stable identifier.
    return undefined;
  }
}

function storeSessionId(sessionId: string): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(STORAGE_KEY, sessionId);
  } catch {
    return;
  }
}
