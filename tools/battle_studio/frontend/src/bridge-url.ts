export const DEFAULT_PC_BRIDGE_URL = "http://DESKTOP-C3RJG3V:8000/";
export const BRIDGE_STORAGE_KEY = "black.bridgeUrl";

type BridgeLocation = {
  href: string;
  hostname: string;
  origin: string;
};

export function resolveInitialBridgeUrl({
  location,
  storedUrl,
  environmentUrl,
}: {
  location: BridgeLocation;
  storedUrl?: string | null;
  environmentUrl?: string | null;
}): string {
  const queryUrl = new URL(location.href).searchParams.get("bridge")?.trim();
  if (queryUrl) return new URL(queryUrl).toString();

  const stored = storedUrl?.trim();
  if (stored) {
    try { return new URL(stored).toString(); }
    catch { /* ignore an obsolete invalid value */ }
  }

  const configured = environmentUrl?.trim();
  if (configured) return new URL(configured).toString();

  if (!location.hostname.endsWith("github.io")) {
    return new URL(location.origin).toString();
  }

  return DEFAULT_PC_BRIDGE_URL;
}

export function getInitialBridgeUrl(): string {
  const value = resolveInitialBridgeUrl({
    location: window.location,
    storedUrl: window.localStorage.getItem(BRIDGE_STORAGE_KEY),
    environmentUrl: import.meta.env.VITE_LIVE_BASE_URL,
  });
  window.localStorage.setItem(BRIDGE_STORAGE_KEY, value);
  return value;
}

export function persistBridgeUrl(value: string): string {
  const normalized = new URL(value.trim()).toString();
  window.localStorage.setItem(BRIDGE_STORAGE_KEY, normalized);
  return normalized;
}
