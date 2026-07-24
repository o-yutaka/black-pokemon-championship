import { describe, expect, it } from "vitest";
import { findEngineFile, folderFromInput, type PickedFolder } from "./folderPicker";

function namedFile(name: string, path: string): File {
  const file = new File(["x"], name);
  Object.defineProperty(file, "webkitRelativePath", { value: path });
  return file;
}

describe("easy folder picker", () => {
  it("uses the selected top folder name and ignores virtual environments", () => {
    const files = {
      0: namedFile("main.py", "agent/main.py"),
      1: namedFile("deck.csv", "agent/deck.csv"),
      2: namedFile("junk.py", "agent/.venv/lib/junk.py"),
      length: 3,
      item(index: number) { return (this as Record<number, File>)[index] ?? null; },
    } as unknown as FileList;
    const folder = folderFromInput(files);
    expect(folder?.name).toBe("agent");
    expect(folder?.files.map((entry) => entry.path)).toEqual(["agent/main.py", "agent/deck.csv"]);
  });

  it("prefers the shallowest libcg.so over ZIP files", () => {
    const folder: PickedFolder = {
      name: "engine",
      files: [
        { file: new File(["zip"], "engine.zip"), path: "downloads/engine.zip" },
        { file: new File(["elf"], "libcg.so"), path: "submission/cg/libcg.so" },
        { file: new File(["elf2"], "libcg.so"), path: "archive/old/cg/libcg.so" },
      ],
    };
    expect(findEngineFile(folder).path).toBe("submission/cg/libcg.so");
  });
});
