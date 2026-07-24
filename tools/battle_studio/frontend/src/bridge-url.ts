export const DEFAULT_PC_BRIDGE_URL = "http://127.0.0.1:8000/";
export const DEFAULT_IPHONE_BRIDGE_URL = "http://DESKTOP-C3RJG3V:8000/";
export const LEGACY_DESKTOP_BRIDGE_URL = DEFAULT_IPHONE_BRIDGE_URL;
export const BRIDGE_STORAGE_KEY = "black.bridgeUrl";

type BridgeLocation = {
  href: string;
  hostname: string;
  origin: string;
};

export function detectIosBridgeClient(): boolean {
  return /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}

export function resolveInitialBridgeUrl({
  location,
  storedUrl,
  environmentUrl,
  isIos = false,
}: {
  location: BridgeLocation;
  storedUrl?: string | null;
  environmentUrl?: string | null;
  isIos?: boolean;
}): string {
  const queryUrl = new URL(location.href).searchParams.get("bridge")?.trim();
  if (queryUrl) return new URL(queryUrl).toString();

  const stored = storedUrl?.trim();
  if (stored) {
    try {
      const normalized = new URL(stored).toString();
      const legacyDesktopValue = !isIos && normalized === LEGACY_DESKTOP_BRIDGE_URL;
      if (!legacyDesktopValue) return normalized;
    } catch {
      // Ignore obsolete invalid values.
    }
  }

  const configured = environmentUrl?.trim();
  if (configured) {
    const normalized = new URL(configured).toString();
    if (isIos || normalized !== LEGACY_DESKTOP_BRIDGE_URL) return normalized;
  }

  if (!location.hostname.endsWith("github.io")) {
    return new URL(location.origin).toString();
  }

  return isIos ? DEFAULT_IPHONE_BRIDGE_URL : DEFAULT_PC_BRIDGE_URL;
}

export function getInitialBridgeUrl(): string {
  const value = resolveInitialBridgeUrl({
    location: window.location,
    storedUrl: window.localStorage.getItem(BRIDGE_STORAGE_KEY),
    environmentUrl: import.meta.env.VITE_LIVE_BASE_URL,
    isIos: detectIosBridgeClient(),
  });
  window.localStorage.setItem(BRIDGE_STORAGE_KEY, value);
  return value;
}

export function persistBridgeUrl(value: string): string {
  const normalized = new URL(value.trim()).toString();
  window.localStorage.setItem(BRIDGE_STORAGE_KEY, normalized);
  return normalized;
}
