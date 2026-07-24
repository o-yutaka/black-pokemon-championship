import { describe, expect, it } from "vitest";
import { DEFAULT_UI_LOCALE, initializeJapaneseUi, liveStatusJa, UI_LOCALE_STORAGE_KEY } from "./locale";

describe("Japanese UI persistence", () => {
  it("stores Japanese and restores the document language", () => {
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

  it("replaces an obsolete non-Japanese value", () => {
    const values = new Map([[UI_LOCALE_STORAGE_KEY, "en"]]);
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
    };
    initializeJapaneseUi(storage, { lang: "", dataset: {} });
    expect(values.get(UI_LOCALE_STORAGE_KEY)).toBe("ja");
  });

  it("renders connection states in Japanese", () => {
    expect(liveStatusJa("disconnected")).toBe("未接続");
    expect(liveStatusJa("connected")).toBe("接続済み");
    expect(liveStatusJa("runner-missing")).toBe("Bridge接続済み");
  });
});
