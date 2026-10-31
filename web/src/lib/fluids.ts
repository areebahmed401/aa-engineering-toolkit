// Mirrors engtoolkit.materials.needs_fluid_library: plain CoolProp names use the HEOS library,
// which takes about a minute to load the first time in the browser.
export const TABULATED_AIR = "Air (1 atm table)";

export function needsFluidLibrary(name: unknown): boolean {
  if (typeof name !== "string" || !name || name === TABULATED_AIR) return false;
  const idx = name.lastIndexOf("::");
  const backend = idx === -1 ? "" : name.slice(0, idx).toUpperCase();
  return backend === "" || backend === "HEOS";
}

/** True if any fluid-like input of a tool will need the HEOS library. */
export function inputsNeedFluidLibrary(values: Record<string, unknown>): boolean {
  return ["fluid", "refrigerant"].some((k) => needsFluidLibrary(values[k]));
}
