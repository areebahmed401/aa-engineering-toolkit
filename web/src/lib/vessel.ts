// Helpers for the pressure vessel builder page (asme.vessel_design): display units and the report.
import type { ResultField } from "./types";
import { formatNumber, type UnitSystem } from "./units";

export type VesselCheck = {
  item: string;
  clause: string;
  required: number;
  provided: number;
  unit: string;
  status: "PASS" | "FAIL";
};

export type VesselPart = { name: string; fields: ResultField[] };

// Vessel-friendly display units: thickness in mm / in, pressure in MPa / psi, area in mm² / in².
const VESSEL_UNITS: Record<string, Record<UnitSystem, [string, number]>> = {
  m: { SI: ["mm", 1e-3], Imperial: ["in", 0.0254] },
  Pa: { SI: ["MPa", 1e6], Imperial: ["psi", 6894.757293168] },
  "m^2": { SI: ["mm²", 1e-6], Imperial: ["in²", 0.00064516] },
};

export function vesselUnit(siUnit: string, system: UnitSystem): string {
  return VESSEL_UNITS[siUnit]?.[system][0] ?? siUnit;
}

export function vesselValue(value: unknown, siUnit: string, system: UnitSystem): string {
  if (typeof value !== "number") return formatNumber(value);
  const conv = VESSEL_UNITS[siUnit]?.[system];
  return formatNumber(conv ? value / conv[1] : value);
}

export function withUnit(value: unknown, siUnit: string, system: UnitSystem): string {
  const unit = vesselUnit(siUnit, system);
  const shown = vesselValue(value, siUnit, system);
  return unit && shown !== "—" ? `${shown} ${unit}` : shown;
}

export function field<T = unknown>(fields: ResultField[], name: string): T | undefined {
  return fields.find((f) => f.name === name)?.value as T | undefined;
}

/** Checks table, notes and disclaimer appended to the standard Markdown report. */
export function vesselReportSections(fields: ResultField[], system: UnitSystem): string {
  const checks = field<VesselCheck[]>(fields, "checks") ?? [];
  const notes = field<string[]>(fields, "notes") ?? [];
  const disclaimer = field<string>(fields, "disclaimer") ?? "";
  const lines = [
    "## Checks",
    "",
    "| Item | Clause | Required | Provided | Status |",
    "|---|---|---|---|---|",
    ...checks.map(
      (c) => `| ${c.item} | ${c.clause} | ${withUnit(c.required, c.unit, system)} | ${withUnit(c.provided, c.unit, system)} | ${c.status} |`,
    ),
  ];
  if (notes.length) lines.push("", "## Notes", "", ...notes.map((n) => `- ${n}`));
  if (disclaimer) lines.push("", `> ${disclaimer}`);
  return lines.join("\n") + "\n";
}
