import { describe, expect, it } from "vitest";
import { buildOpponentPresets, compatibleWithEngine, loadStoredOpponent, opponentDisplayName, preferredOpponent, saveStoredOpponent, type PresetBundle } from "./opponent-presets";

const engine = { id: "engine-1", sha256: "engine-sha" };
const bundle = (id: string, filename: string, sha256: string, bundledEngineSha256: string | null = null): PresetBundle => ({ id, filename, sha256, deckCount: 60, uniqueCardIds: 20, bundledEngineSha256 });

describe("相手プリセット", () => {
  it("前回の相手を最優先し、無ければ自分ミラーを選ぶ", () => {
    const player = bundle("player", "dragapult_agent", "player-sha");
    const previous = bundle("previous", "rocket_mewtwo", "previous-sha");
    const presets = buildOpponentPresets({ engine, player, bundles: [player, previous], stored: { bundleSha256: previous.sha256, filename: previous.filename } });
    expect(preferredOpponent(presets)?.id).toBe("previous");
    const withoutPrevious = buildOpponentPresets({ engine, player, bundles: [player], stored: null });
    expect(preferredOpponent(withoutPrevious)?.id).toBe("player");
  });

  it("公式Engine SHAが違うBundleは候補へ出さない", () => {
    const valid = bundle("valid", "crustle", "valid-sha", "engine-sha");
    const invalid = bundle("invalid", "grimmsnarl", "invalid-sha", "other-engine");
    expect(compatibleWithEngine(valid, engine)).toBe(true);
    expect(compatibleWithEngine(invalid, engine)).toBe(false);
    const presets = buildOpponentPresets({ engine, player: null, bundles: [valid, invalid], stored: null });
    expect(presets.map((item) => item.bundle?.id)).toEqual(["valid"]);
  });

  it("前回BundleがBridgeに無い時は無効表示し、別Bundleへすり替えない", () => {
    const presets = buildOpponentPresets({ engine, player: null, bundles: [], stored: { bundleSha256: "missing", filename: "rocket" } });
    expect(presets).toHaveLength(1);
    expect(presets[0]).toMatchObject({ kind: "previous", available: false, bundle: null });
    expect(preferredOpponent(presets)).toBeNull();
  });

  it("保存データを安全に読み書きし、表示名はファイル名だけから作る", () => {
    let value: string | null = null;
    const storage = { getItem: () => value, setItem: (_key: string, next: string) => { value = next; } };
    const target = bundle("rocket", "rocket_mewtwo_agent.tar.gz", "rocket-sha");
    saveStoredOpponent(target, storage);
    expect(loadStoredOpponent(storage)).toEqual({ bundleSha256: "rocket-sha", filename: "rocket_mewtwo_agent.tar.gz" });
    expect(opponentDisplayName(target.filename)).toBe("ロケット団・ミュウツー");
  });
});
