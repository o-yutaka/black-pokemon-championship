export const LAST_OPPONENT_STORAGE_KEY = "black.lastOpponentPreset.v1";

export type PresetEngine = { id: string; sha256: string };
export type PresetBundle = {
  id: string;
  filename: string;
  sha256: string;
  deckCount: number;
  uniqueCardIds: number;
  bundledEngineSha256?: string | null;
};

export type StoredOpponentPreset = {
  bundleSha256: string;
  filename: string;
};

export type OpponentPreset = {
  key: string;
  label: string;
  description: string;
  bundle: PresetBundle | null;
  available: boolean;
  reason: string | null;
  kind: "mirror" | "previous" | "registered";
};

export function opponentDisplayName(filename: string): string {
  const value = filename.replace(/\.(?:tar\.gz|tgz|gz)$/i, "").replace(/[_-]+/g, " ").trim();
  const normalized = value.toLowerCase();
  if (/rocket|mewtwo|ロケット|ミュウツー/.test(normalized)) return "ロケット団・ミュウツー";
  if (/grimmsnarl|オーロンゲ/.test(normalized)) return "オーロンゲ";
  if (/crustle|イワパレス/.test(normalized)) return "イワパレス";
  if (/dragapult|ドラパルト/.test(normalized)) return "ドラパルト";
  if (/garchomp|ガブリアス/.test(normalized)) return "ガブリアス";
  return value || "登録済みOpponent";
}

export function compatibleWithEngine(bundle: PresetBundle, engine: PresetEngine | null): boolean {
  if (!engine) return false;
  return !bundle.bundledEngineSha256 || bundle.bundledEngineSha256 === engine.sha256;
}

export function loadStoredOpponent(storage: Pick<Storage, "getItem"> = window.localStorage): StoredOpponentPreset | null {
  try {
    const raw = storage.getItem(LAST_OPPONENT_STORAGE_KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as Partial<StoredOpponentPreset>;
    return typeof value.bundleSha256 === "string" && typeof value.filename === "string" ? { bundleSha256: value.bundleSha256, filename: value.filename } : null;
  } catch { return null; }
}

export function saveStoredOpponent(bundle: PresetBundle, storage: Pick<Storage, "setItem"> = window.localStorage): void {
  storage.setItem(LAST_OPPONENT_STORAGE_KEY, JSON.stringify({ bundleSha256: bundle.sha256, filename: bundle.filename } satisfies StoredOpponentPreset));
}

export function buildOpponentPresets(input: {
  engine: PresetEngine | null;
  player: PresetBundle | null;
  bundles: PresetBundle[];
  stored: StoredOpponentPreset | null;
  limit?: number;
}): OpponentPreset[] {
  const { engine, player, stored } = input;
  const limit = input.limit ?? 6;
  const compatible = input.bundles.filter((bundle) => compatibleWithEngine(bundle, engine));
  const result: OpponentPreset[] = [];
  const used = new Set<string>();
  const add = (preset: OpponentPreset) => {
    const identity = preset.bundle?.sha256 ?? preset.key;
    if (used.has(identity)) return;
    used.add(identity);
    result.push(preset);
  };

  if (player) add({
    key: "mirror",
    label: "自分ミラー",
    description: "現在選択中の自分Agentを相手にも使用",
    bundle: player,
    available: compatibleWithEngine(player, engine),
    reason: compatibleWithEngine(player, engine) ? null : "公式Engine SHAが一致しません",
    kind: "mirror",
  });

  if (stored) {
    const previous = compatible.find((bundle) => bundle.sha256 === stored.bundleSha256) ?? null;
    add({
      key: "previous",
      label: "前回の相手",
      description: previous ? opponentDisplayName(previous.filename) : opponentDisplayName(stored.filename),
      bundle: previous,
      available: Boolean(previous),
      reason: previous ? null : "このBridgeには前回のBundleが未登録です",
      kind: "previous",
    });
  }

  compatible
    .filter((bundle) => bundle.sha256 !== player?.sha256 && bundle.sha256 !== stored?.bundleSha256)
    .sort((left, right) => opponentDisplayName(left.filename).localeCompare(opponentDisplayName(right.filename), "ja") || left.sha256.localeCompare(right.sha256))
    .slice(0, limit)
    .forEach((bundle) => add({
      key: `registered:${bundle.id}`,
      label: opponentDisplayName(bundle.filename),
      description: `${bundle.deckCount}枚 · ${bundle.uniqueCardIds}種類`,
      bundle,
      available: true,
      reason: null,
      kind: "registered",
    }));

  return result;
}

export function preferredOpponent(presets: OpponentPreset[]): PresetBundle | null {
  return presets.find((preset) => preset.kind === "previous" && preset.available)?.bundle
    ?? presets.find((preset) => preset.kind === "mirror" && preset.available)?.bundle
    ?? presets.find((preset) => preset.kind === "registered" && preset.available)?.bundle
    ?? null;
}
