// Downloadable reports: Markdown summary of a calculation and CSV for tables.
import type { FieldSpec } from "./schema";
import type { ResultField, ToolSchema } from "./types";
import { displayUnit, formatNumber, toDisplay, type UnitSystem } from "./units";

function displayValue(value: unknown, unit: string, system: UnitSystem): string {
  return typeof value === "number" ? formatNumber(toDisplay(value, unit, system)) : formatNumber(value);
}

function inputRows(fields: FieldSpec[], values: Record<string, unknown>, system: UnitSystem, prefix = ""): string[] {
  const rows: string[] = [];
  for (const f of fields) {
    const v = values[f.name];
    if (f.kind === "object" && f.fields) {
      rows.push(...inputRows(f.fields, (v as Record<string, unknown>) ?? {}, system, `${prefix}${f.label} › `));
    } else if (f.kind === "array" && Array.isArray(v) && f.item?.fields) {
      v.forEach((item, i) =>
        rows.push(...inputRows(f.item!.fields!, item as Record<string, unknown>, system, `${prefix}${f.label} ${i + 1} › `)),
      );
    } else {
      const unit = f.unit ? displayUnit(f.unit, system) : "";
      rows.push(`| ${prefix}${f.label} | ${displayValue(v, f.unit, system)} | ${unit} |`);
    }
  }
  return rows;
}

export function markdownReport(opts: {
  tool: ToolSchema;
  fields: FieldSpec[];
  values: Record<string, unknown>;
  results: ResultField[];
  system: UnitSystem;
  version: string;
  link: string;
}): string {
  const { tool, fields, values, results, system, version, link } = opts;
  const resultRows = results
    .filter((r) => r.summary && !Array.isArray(r.value) && (typeof r.value !== "object" || r.value === null))
    .map((r) => `| ${r.label} | ${displayValue(r.value, r.unit, system)} | ${r.unit ? displayUnit(r.unit, system) : ""} |`);
  return [
    `# ${tool.name}`,
    "",
    `*AA Engineering Toolkit v${version} · ${new Date().toISOString().slice(0, 16).replace("T", " ")} UTC · ${system} units*`,
    "",
    tool.description,
    "",
    "## Inputs",
    "",
    "| Input | Value | Unit |",
    "|---|---|---|",
    ...inputRows(fields, values, system),
    "",
    "## Results",
    "",
    "| Result | Value | Unit |",
    "|---|---|---|",
    ...resultRows,
    "",
    `**Reference:** ${tool.reference}`,
    "",
    `[Reproduce this calculation](${link})`,
    "",
    "> Preliminary design aid. Verify results against the governing codes and standards before use.",
    "",
  ].join("\n");
}

export function csv(columns: string[], rows: unknown[][]): string {
  const cell = (v: unknown) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [columns.map(cell).join(","), ...rows.map((r) => r.map(cell).join(","))].join("\n") + "\n";
}

export function download(filename: string, text: string, type = "text/plain"): void {
  const url = URL.createObjectURL(new Blob([text], { type: `${type};charset=utf-8` }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
