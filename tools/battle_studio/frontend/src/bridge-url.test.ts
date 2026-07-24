import { describe, expect, it } from "vitest";
import { DEFAULT_IPHONE_BRIDGE_URL, DEFAULT_PC_BRIDGE_URL, resolveInitialBridgeUrl } from "./bridge-url";

const githubLocation = {
  href: "https://o-yutaka.github.io/black-pokemon-championship/",
  hostname: "o-yutaka.github.io",
  origin: "https://o-yutaka.github.io",
};

describe("Bridge URL defaults", () => {
  it("prefills loopback on the user's desktop", () => {
    expect(resolveInitialBridgeUrl({ location: githubLocation, isIos: false })).toBe(DEFAULT_PC_BRIDGE_URL);
  });

  it("prefills the Windows host name on iPhone", () => {
    expect(resolveInitialBridgeUrl({ location: githubLocation, isIos: true })).toBe(DEFAULT_IPHONE_BRIDGE_URL);
  });

  it("migrates the obsolete desktop host-name value to loopback", () => {
    expect(resolveInitialBridgeUrl({
      location: githubLocation,
      storedUrl: DEFAULT_IPHONE_BRIDGE_URL,
      isIos: false,
    })).toBe(DEFAULT_PC_BRIDGE_URL);
  });

  it("keeps the last valid LAN URL", () => {
    expect(resolveInitialBridgeUrl({
      location: githubLocation,
      storedUrl: "http://192.168.1.25:8000",
      isIos: true,
    })).toBe("http://192.168.1.25:8000/");
  });

  it("allows a bridge query parameter to override the saved value", () => {
    expect(resolveInitialBridgeUrl({
      location: { ...githubLocation, href: `${githubLocation.href}?bridge=http%3A%2F%2F10.0.0.8%3A8000` },
      storedUrl: "http://192.168.1.25:8000",
    })).toBe("http://10.0.0.8:8000/");
  });

  it("uses the current origin when opened from the Bridge itself", () => {
    expect(resolveInitialBridgeUrl({
      location: {
        href: "http://192.168.1.25:8000/",
        hostname: "192.168.1.25",
        origin: "http://192.168.1.25:8000",
      },
    })).toBe("http://192.168.1.25:8000/");
  });
});
