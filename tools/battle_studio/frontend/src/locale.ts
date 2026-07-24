export const UI_LOCALE_STORAGE_KEY = "black.uiLocale";
export const DEFAULT_UI_LOCALE = "ja";

export function initializeJapaneseUi(storage: Pick<Storage, "getItem" | "setItem"> = window.localStorage, root: HTMLElement = document.documentElement): "ja" {
  const stored = storage.getItem(UI_LOCALE_STORAGE_KEY);
  if (stored !== DEFAULT_UI_LOCALE) storage.setItem(UI_LOCALE_STORAGE_KEY, DEFAULT_UI_LOCALE);
  root.lang = DEFAULT_UI_LOCALE;
  root.dataset.uiLocale = DEFAULT_UI_LOCALE;
  return DEFAULT_UI_LOCALE;
}

export function liveStatusJa(status: string): string {
  const labels: Record<string, string> = {
    disconnected: "未接続",
    connecting: "接続中",
    connected: "接続済み",
    closed: "切断済み",
    error: "エラー",
    checking: "確認中",
    ready: "接続済み",
    "runner-missing": "Bridge接続済み",
    offline: "未接続",
  };
  return labels[status] ?? status;
}
