import { describe, expect, it } from "vitest";
import { demoReplay } from "./demo";
import { battleReplaySchema } from "./types";

describe("BLACK Decision IDE", () => {
  it("parses the full layered demo contract", () => {
    const replay = battleReplaySchema.parse(demoReplay);
    const decision = replay.frames[0].decision;
    expect(decision?.decisionId).toBe("184");
    expect(decision?.searchTree?.children.find((node) => node.status === "selected")?.label).toBe("Ability");
    expect(decision?.rejectedBranches?.[0].killedBy).toContain("CLOCK_V3");
    expect(decision?.policyTrace?.find((policy) => policy.name === "BossPolicy")?.status).toBe("FAIL");
    expect(decision?.route?.currentStep).toBe(3);
    expect(decision?.truthLedger?.Truth).toBe("PASS");
  });

  it("keeps legacy decision frames valid", () => {
    const legacy = structuredClone(demoReplay);
    legacy.frames[0].decision = {
      actor: 0,
      goal: "legacy",
      chosen: "[0]",
      confidence: null,
      elapsedMs: null,
      candidates: [],
    };
    const replay = battleReplaySchema.parse(legacy);
    expect(replay.frames[0].decision?.searchTree).toBeUndefined();
  });
});
