const MIXED_CONTENT_MESSAGE = "公開サイトからPC内Bridgeへの通信はブラウザに遮断されます。WSL2でBridgeを起動し、http://127.0.0.1:8000/ を直接開いてください。";
const OFFLINE_MESSAGE = "Bridgeへ接続できません。WSL2で bash tools/battle_studio/start_bridge.sh を実行してください。";

export function isLocalBridgeUrl(url: URL): boolean {
  return url.protocol === "http:" && (
    url.hostname === "127.0.0.1" ||
    url.hostname === "localhost" ||
    url.hostname.toUpperCase() === "DESKTOP-C3RJG3V" ||
    /^10\./.test(url.hostname) ||
    /^192\.168\./.test(url.hostname) ||
    /^172\.(1[6-9]|2\d|3[01])\./.test(url.hostname)
  );
}

export function friendlyBridgeError(error: unknown, target: URL, pageProtocol = window.location.protocol): Error {
  if (pageProtocol === "https:" && target.protocol === "http:") return new Error(MIXED_CONTENT_MESSAGE);
  if (isLocalBridgeUrl(target) && (error instanceof TypeError || (error instanceof Error && error.message === "Failed to fetch"))) return new Error(OFFLINE_MESSAGE);
  return error instanceof Error ? error : new Error(String(error));
}

export function installJapaneseNetworkErrors(): void {
  const originalFetch = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const target = new URL(input instanceof Request ? input.url : String(input), window.location.href);
    if (window.location.protocol === "https:" && target.protocol === "http:") {
      throw new Error(MIXED_CONTENT_MESSAGE);
    }
    try {
      return await originalFetch(input, init);
    } catch (error) {
      throw friendlyBridgeError(error, target);
    }
  };
}
