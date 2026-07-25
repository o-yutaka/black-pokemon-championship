import { describe, expect, it } from "vitest";
import { demoReplay } from "./demo";
import { parseReplay, ReplayValidationError } from "./replay";
import { cardKey } from "./types";

const frame = demoReplay.frames[0];

describe("replay truth contract", () => {
  it("accepts the deterministic demo replay", () => {
    const replay = parseReplay(demoReplay);
    expect(replay.frames).toHaveLength(3);
    expect(cardKey(replay.frames[0].players[0].active!)).toBe("0:1001");
  });

  it("rejects a duplicate per-match card instance inside one frame", () => {
    const broken = structuredClone(demoReplay);
    broken.frames[0].players[0].bench.push({ ...broken.frames[0].players[0].active!, zone: "bench", slot: 4 });
    expect(() => parseReplay(broken)).toThrow(ReplayValidationError);
  });

  it("does not confuse equal card ids with different serials", () => {
    const valid = structuredClone(demoReplay);
    const original = valid.frames[0].players[0].bench[0];
    valid.frames[0].players[0].bench.push({ ...original, serial: original.serial + 500, slot: 4 });
    expect(() => parseReplay(valid)).not.toThrow();
  });

  it("fails closed when required frame state is absent", () => {
    const broken = structuredClone(demoReplay) as unknown as { frames: unknown[] };
    broken.frames[0] = { frameId: 0 };
    expect(() => parseReplay(broken)).toThrow(ReplayValidationError);
  });
});

describe("対戦記録のかんたん読み込み", () => {
  it("Bridge Snapshot単体をReplayへ変換する", () => {
    const parsed = parseReplay({
      type: "snapshot",
      sessionId: "session-1",
      engine: "official-battle",
      publicProtocol: "1.1",
      hiddenInformationPolicy: "player_view",
      frame,
    });
    expect(parsed.replayId).toBe("session-1");
    expect(parsed.source).toBe("cabt");
    expect(parsed.frames).toHaveLength(1);
  });

  it("Frame単体をそのまま開ける", () => {
    const parsed = parseReplay(frame);
    expect(parsed.schemaVersion).toBe("1.0");
    expect(parsed.frames[0].frameId).toBe(frame.frameId);
  });

  it("frames配列だけのJSONを開ける", () => {
    const parsed = parseReplay({ frames: [frame] });
    expect(parsed.frames).toHaveLength(1);
    expect(parsed.source).toBe("unknown");
  });

  it("生配列も対戦記録として開ける", () => {
    const parsed = parseReplay([frame]);
    expect(parsed.frames).toHaveLength(1);
  });

  it("無関係なJSONでは内部Schema名を表示しない", () => {
    expect(() => parseReplay({ hello: "world" })).toThrow(ReplayValidationError);
    try {
      parseReplay({ hello: "world" });
    } catch (error) {
      expect(String(error)).not.toContain("schemaVersion");
      expect(String(error)).not.toContain("Invalid input");
      expect(String(error)).toContain("対戦記録");
    }
  });
});
