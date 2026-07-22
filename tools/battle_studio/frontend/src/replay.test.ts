import { describe, expect, it } from "vitest";
import { demoReplay } from "./demo";
import { parseReplay, ReplayValidationError } from "./replay";
import { cardKey } from "./types";

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
