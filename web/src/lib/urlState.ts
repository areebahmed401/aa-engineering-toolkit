// Encode tool inputs (SI values) in the URL so a link reproduces the calculation.

function toBase64Url(text: string): string {
  const bytes = new TextEncoder().encode(text);
  let bin = "";
  bytes.forEach((b) => (bin += String.fromCharCode(b)));
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromBase64Url(data: string): string {
  const b64 = data.replace(/-/g, "+").replace(/_/g, "/");
  const bin = atob(b64 + "===".slice((b64.length + 3) % 4));
  return new TextDecoder().decode(Uint8Array.from(bin, (c) => c.charCodeAt(0)));
}

/** Only the values that differ from the defaults are encoded. */
export function encodeInputs(values: Record<string, unknown>, defaults: Record<string, unknown>): string {
  const changed: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(values)) {
    if (JSON.stringify(v) !== JSON.stringify(defaults[k])) changed[k] = v;
  }
  return Object.keys(changed).length ? toBase64Url(JSON.stringify(changed)) : "";
}

export function decodeInputs(data: string | null): Record<string, unknown> {
  if (!data) return {};
  try {
    const parsed = JSON.parse(fromBase64Url(data));
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}
