import { describe, expect, it } from "vitest";
import { DEFAULT_UI_LOCALE, initializeJapaneseUi, liveStatusJa, UI_LOCALE_STORAGE_KEY } from "./locale";

describe("日本語UIの保持", () => {
  it("日本語設定を保存して文書言語へ反映する", () => {
    const values = new Map<string, string>();
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
    };
    const root = { lang: "", dataset: {} as Record<string, string | undefined> };
    expect(initializeJapaneseUi(storage, root)).toBe(DEFAULT_UI_LOCALE);
    expect(values.get(UI_LOCALE_STORAGE_KEY)).toBe("ja");
    expect(root.lang).toBe("ja");
    expect(root.dataset.uiLocale).toBe("ja");
  });

  it("古い日本語以外の設定を置き換える", () => {
    const values = new Map([[UI_LOCALE_STORAGE_KEY, "en"]]);
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
    };
    initializeJapaneseUi(storage, { lang: "", dataset: {} });
    expect(values.get(UI_LOCALE_STORAGE_KEY)).toBe("ja");
  });

  it("接続状態を日本語で表示する", () => {
    expect(liveStatusJa("disconnected")).toBe("未接続");
    expect(liveStatusJa("connected")).toBe("接続済み");
    expect(liveStatusJa("runner-missing")).toBe("接続先確認済み");
  });
});
