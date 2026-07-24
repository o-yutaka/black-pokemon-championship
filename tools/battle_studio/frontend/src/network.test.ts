import { describe, expect, it } from "vitest";
import { friendlyBridgeError, isLocalBridgeUrl } from "./network";

describe("Japanese Bridge network errors", () => {
  it("recognizes loopback and private LAN Bridge URLs", () => {
    expect(isLocalBridgeUrl(new URL("http://127.0.0.1:8000/api/health"))).toBe(true);
    expect(isLocalBridgeUrl(new URL("http://192.168.1.20:8000/api/health"))).toBe(true);
    expect(isLocalBridgeUrl(new URL("https://example.com"))).toBe(false);
  });

  it("explains HTTPS to HTTP blocking in Japanese", () => {
    const error = friendlyBridgeError(new TypeError("Failed to fetch"), new URL("http://127.0.0.1:8000/api/health"), "https:");
    expect(error.message).toContain("公開サイト");
    expect(error.message).toContain("直接開いてください");
  });

  it("replaces browser Failed to fetch with the WSL2 command", () => {
    const error = friendlyBridgeError(new TypeError("Failed to fetch"), new URL("http://127.0.0.1:8000/api/health"), "http:");
    expect(error.message).toContain("start_bridge.sh");
  });
});
