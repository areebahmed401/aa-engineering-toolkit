// Display units. Python works in SI; the UI converts at the edges (SI or Imperial display).

export type UnitSystem = "SI" | "Imperial";

type Conv = { unit: string; toSI: (v: number) => number; fromSI: (v: number) => number };

const lin = (unit: string, factor: number): Conv => ({ unit, toSI: (v) => v * factor, fromSI: (v) => v / factor });
const same = (unit: string): Conv => lin(unit, 1);

// SI unit (as written by the Python package) -> display conversion per unit system
const TABLE: Record<string, Record<UnitSystem, Conv>> = {
  K: {
    SI: { unit: "°C", toSI: (v) => v + 273.15, fromSI: (v) => v - 273.15 },
    Imperial: { unit: "°F", toSI: (v) => (v - 32) / 1.8 + 273.15, fromSI: (v) => (v - 273.15) * 1.8 + 32 },
  },
  "ΔK": { SI: lin("Δ°C", 1), Imperial: lin("Δ°F", 1 / 1.8) },
  Pa: { SI: lin("kPa", 1e3), Imperial: lin("psi", 6894.757293168) },
  "J/kg": { SI: lin("kJ/kg", 1e3), Imperial: lin("Btu/lb", 2326) },
  "J/(kg·K)": { SI: lin("kJ/(kg·K)", 1e3), Imperial: lin("Btu/(lb·°F)", 4186.8) },
  W: { SI: lin("kW", 1e3), Imperial: lin("Btu/h", 0.29307107) },
  "W/m": { SI: same("W/m"), Imperial: lin("Btu/(h·ft)", 0.96152) },
  "W/(m²·K)": { SI: same("W/(m²·K)"), Imperial: lin("Btu/(h·ft²·°F)", 5.678263) },
  "W/(m·K)": { SI: same("W/(m·K)"), Imperial: lin("Btu/(h·ft·°F)", 1.730735) },
  "m·K/W": { SI: same("m·K/W"), Imperial: lin("h·ft·°F/Btu", 1 / 0.96152 / 1.8) },
  m: { SI: same("m"), Imperial: lin("ft", 0.3048) },
  "m/s": { SI: same("m/s"), Imperial: lin("ft/s", 0.3048) },
  "m^2": { SI: lin("cm²", 1e-4), Imperial: lin("in²", 0.00064516) },
  "m^3": { SI: lin("cm³", 1e-6), Imperial: lin("in³", 1.6387064e-5) },
  "m^4": { SI: lin("cm⁴", 1e-8), Imperial: lin("in⁴", 4.162314256e-7) },
  "m^6": { SI: lin("cm⁶", 1e-12), Imperial: lin("in⁶", 6.9286e-11) },
  "m^3/s": { SI: lin("m³/h", 1 / 3600), Imperial: lin("gpm", 6.30901964e-5) },
  "m^3/kg": { SI: same("m³/kg"), Imperial: lin("ft³/lb", 0.06242796) },
  "kg/s": { SI: same("kg/s"), Imperial: lin("lb/s", 0.45359237) },
  "kg/m^3": { SI: same("kg/m³"), Imperial: lin("lb/ft³", 16.01846337) },
  "kg/m": { SI: same("kg/m"), Imperial: lin("lb/ft", 1.48816394) },
  "kg/kg": { SI: same("kg/kg"), Imperial: same("lb/lb") },
  "kg/mol": { SI: lin("g/mol", 1e-3), Imperial: lin("lb/lbmol", 1e-3) },
  "Pa·s": { SI: lin("mPa·s", 1e-3), Imperial: lin("cP", 1e-3) },
  N: { SI: lin("kN", 1e3), Imperial: lin("lbf", 4.448221615) },
  "N·m": { SI: lin("kN·m", 1e3), Imperial: lin("lbf·ft", 1.355817948) },
  "N/m": { SI: lin("kN/m", 1e3), Imperial: lin("lbf/ft", 14.59390294) },
  rad: { SI: same("rad"), Imperial: same("rad") },
  deg: { SI: same("°"), Imperial: same("°") },
  USD: { SI: same("USD"), Imperial: same("USD") },
};

const TABLE_ALIASES: Record<string, string> = { "W/(m2·K)": "W/(m²·K)" };

export function conversion(siUnit: string, system: UnitSystem): Conv {
  const key = TABLE_ALIASES[siUnit] ?? siUnit;
  return TABLE[key]?.[system] ?? same(siUnit);
}

export function displayUnit(siUnit: string, system: UnitSystem): string {
  return conversion(siUnit, system).unit;
}

export function toDisplay(value: number, siUnit: string, system: UnitSystem): number {
  return conversion(siUnit, system).fromSI(value);
}

export function toSI(value: number, siUnit: string, system: UnitSystem): number {
  return conversion(siUnit, system).toSI(value);
}

/** Format a number with ~4 significant figures, switching to exponent form for very large/small values. */
export function formatNumber(value: unknown, digits = 4): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value !== "number") return String(value);
  if (!Number.isFinite(value)) return "—";
  if (value === 0) return "0";
  const abs = Math.abs(value);
  if (abs >= 1e6 || abs < 1e-3) return value.toExponential(digits - 1).replace("e+", "e");
  const s = value.toPrecision(digits);
  return s.includes(".") && !s.includes("e") ? s.replace(/\.?0+$/, "") : s;
}

/** Value for an input box: display units, trimmed to a sensible precision. */
export function inputString(siValue: number, siUnit: string, system: UnitSystem): string {
  const v = toDisplay(siValue, siUnit, system);
  return String(Number.parseFloat(v.toPrecision(8)));
}
