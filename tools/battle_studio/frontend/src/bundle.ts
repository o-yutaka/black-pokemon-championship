export type BundleInfo = {
  bundleId: string;
  archiveSha256: string;
  engineSha256: string;
  deckCount: number;
  deck: number[];
  members: string[];
};

export async function uploadKaggleBundle(baseUrl: string, file: File): Promise<BundleInfo> {
  const form = new FormData();
  form.append("file", file, file.name);
  const response = await fetch(new URL("/api/bundles", baseUrl), { method: "POST", body: form });
  const value = await response.json().catch(() => ({})) as Record<string, unknown>;
  if (!response.ok) throw new Error(String(value.detail ?? `Bundle upload failed: HTTP ${response.status}`));
  if (typeof value.bundleId !== "string" || !Array.isArray(value.deck) || value.deck.length !== 60) {
    throw new Error("Bridge returned an invalid bundle result");
  }
  return value as unknown as BundleInfo;
}
