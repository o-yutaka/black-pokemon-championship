import { deckCsv } from "./deck-easy";

export type FolderFile = { file: File; path: string };
export type PickedFolder = { name: string; files: FolderFile[] };

type FileHandle = { kind: "file"; name: string; getFile(): Promise<File> };
type DirectoryHandle = { kind: "directory"; name: string; values(): AsyncIterable<FileHandle | DirectoryHandle> };
type DirectoryPickerWindow = Window & { showDirectoryPicker?: () => Promise<DirectoryHandle> };

const IGNORED_PARTS = new Set([".git", "node_modules", "__pycache__", ".venv", ".venv-battle-studio", ".DS_Store"]);

function allowed(path: string): boolean {
  return !path.split("/").some((part) => IGNORED_PARTS.has(part) || part.startsWith(".venv"));
}

async function walk(handle: DirectoryHandle, prefix = ""): Promise<FolderFile[]> {
  const result: FolderFile[] = [];
  for await (const entry of handle.values()) {
    const path = prefix ? `${prefix}/${entry.name}` : entry.name;
    if (!allowed(path)) continue;
    if (entry.kind === "file") result.push({ file: await entry.getFile(), path });
    else result.push(...await walk(entry, path));
  }
  return result;
}

export async function chooseFolder(): Promise<PickedFolder | null> {
  const picker = (window as DirectoryPickerWindow).showDirectoryPicker;
  if (!picker) return null;
  try {
    const handle = await picker.call(window);
    return { name: handle.name, files: await walk(handle) };
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") return { name: "", files: [] };
    throw error;
  }
}

export function folderFromInput(files: FileList | null): PickedFolder | null {
  if (!files?.length) return null;
  const selected = Array.from(files).map((file) => ({
    file,
    path: (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name,
  })).filter((entry) => allowed(entry.path));
  const first = selected[0]?.path.split("/")[0] || "選択フォルダー";
  return { name: first, files: selected };
}

export function appendFolder(form: FormData, folder: PickedFolder): void {
  form.append("folder_name", folder.name || "選択フォルダー");
  for (const entry of folder.files) {
    form.append("files", entry.file, entry.file.name);
    form.append("paths", entry.path);
  }
}

export function findEngineFile(folder: PickedFolder): FolderFile {
  const libraries = folder.files.filter((entry) => entry.path.toLowerCase().endsWith("/libcg.so") || entry.path.toLowerCase() === "libcg.so")
    .sort((left, right) => left.path.split("/").length - right.path.split("/").length);
  if (libraries.length) return libraries[0];
  const archives = folder.files.filter((entry) => entry.file.name.toLowerCase().endsWith(".zip"))
    .sort((left, right) => left.path.split("/").length - right.path.split("/").length);
  if (archives.length) return archives[0];
  throw new Error("選択フォルダー内に libcg.so または公式エンジンZIPがありません");
}

function parentPath(path: string): string {
  const parts = path.replace(/\\/g, "/").split("/");
  parts.pop();
  return parts.join("/");
}

export function replaceAgentDeck(folder: PickedFolder, ids: number[]): PickedFolder {
  const mainParents = new Set(folder.files.filter((entry) => entry.file.name.toLowerCase() === "main.py").map((entry) => parentPath(entry.path)));
  const deckCandidates = folder.files.filter((entry) => entry.file.name.toLowerCase() === "deck.csv" && mainParents.has(parentPath(entry.path)));
  if (deckCandidates.length !== 1) throw new Error(`main.pyと同じ場所のdeck.csvを1つだけ含めてください（検出${deckCandidates.length}件）`);
  const targetPath = deckCandidates[0].path;
  const replacement = new File([deckCsv(ids)], "deck.csv", { type: "text/csv;charset=utf-8", lastModified: Date.now() });
  return {
    name: folder.name,
    files: folder.files.map((entry) => entry.path === targetPath ? { file: replacement, path: targetPath } : entry),
  };
}
