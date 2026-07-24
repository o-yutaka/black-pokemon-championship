import { describe, expect, it } from "vitest";
import { deckCsv, parseDeckCsv } from "./deck-easy";
import { replaceAgentDeck, type PickedFolder } from "./folderPicker";

function file(name: string, text: string): File {
  return new File([text], name, { type: "text/plain" });
}

describe("かんたんデッキ操作", () => {
  it("60枚の改行CSVとヘッダー付きCSVを読み込める", () => {
    const ids = Array.from({ length: 60 }, (_, index) => index + 1);
    expect(parseDeckCsv(deckCsv(ids))).toEqual(ids);
    expect(parseDeckCsv(`card_id\n${ids.join("\n")}`)).toEqual(ids);
  });

  it("60枚でないCSVと不正な値を日本語エラーで止める", () => {
    expect(() => parseDeckCsv("1\n2\n3\n")).toThrow("60枚必要");
    expect(() => parseDeckCsv(`${Array.from({ length: 59 }, () => "1").join("\n")}\nabc`)).toThrow("カードIDではない値");
  });

  it("main.pyと同じ場所のdeck.csvだけを差し替える", async () => {
    const folder: PickedFolder = {
      name: "agent",
      files: [
        { path: "agent/main.py", file: file("main.py", "def agent(): pass") },
        { path: "agent/deck.csv", file: file("deck.csv", "1\n") },
        { path: "agent/data/deck.csv", file: file("deck.csv", "old") },
      ],
    };
    const ids = Array.from({ length: 60 }, () => 42);
    const replaced = replaceAgentDeck(folder, ids);
    const mainDeck = replaced.files.find((entry) => entry.path === "agent/deck.csv");
    const dataDeck = replaced.files.find((entry) => entry.path === "agent/data/deck.csv");
    expect(await mainDeck?.file.text()).toBe(deckCsv(ids));
    expect(await dataDeck?.file.text()).toBe("old");
  });
});
