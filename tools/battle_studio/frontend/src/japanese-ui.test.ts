import { describe, expect, it } from "vitest";
import { catalogTermJa, energyJa, liveStatusJa, motionModeJa, phaseJa, zoneJa } from "./locale";

describe("日本語UI用語", () => {
  it("対戦状態と場所を日本語化する", () => {
    expect(liveStatusJa("connected")).toBe("接続済み");
    expect(phaseJa("attack")).toBe("ワザ");
    expect(zoneJa("discard")).toBe("トラッシュ");
  });

  it("カード分類・エネルギー・演出設定を日本語化する", () => {
    expect(catalogTermJa("Stage 2")).toBe("2進化");
    expect(catalogTermJa("Supporter")).toBe("サポート");
    expect(energyJa("Psychic")).toBe("超");
    expect(motionModeJa("balanced")).toBe("軽量");
  });
});
