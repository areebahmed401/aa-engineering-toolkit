import { Download } from "lucide-react";
import { usePrefs } from "../lib/prefs";
import { csv, download } from "../lib/report";
import type { ResultField } from "../lib/types";
import { displayUnit, formatNumber, toDisplay, type UnitSystem } from "../lib/units";

// SI units of the keys used inside nested result lists (e.g. cycle states)
const NESTED_UNITS: Record<string, string> = { T: "K", P: "Pa", h: "J/kg", s: "J/(kg·K)", rho: "kg/m^3" };

function show(value: unknown, unit: string, system: UnitSystem) {
  return typeof value === "number" && unit ? formatNumber(toDisplay(value, unit, system)) : formatNumber(value);
}

export function ResultsView({ fields, toolId }: { fields: ResultField[]; toolId: string }) {
  const { units } = usePrefs();
  const scalars = fields.filter((f) => f.summary && (typeof f.value !== "object" || f.value === null));
  const texts = scalars.filter((f) => typeof f.value === "string");
  const numbers = scalars.filter((f) => typeof f.value !== "string");
  const columns = fields.find((f) => f.name === "columns")?.value as string[] | undefined;
  const rows = fields.find((f) => f.name === "rows")?.value as unknown[][] | undefined;
  const nestedLists = fields.filter(
    (f) => Array.isArray(f.value) && f.value.length > 0 && typeof f.value[0] === "object" && !Array.isArray(f.value[0]),
  );

  return (
    <div className="space-y-4" data-testid="results">
      {texts.length > 0 && (
        <div className="space-y-2">
          {texts.map((f) => (
            <div key={f.name} className="rounded-xl bg-bg px-3 py-2 text-sm">
              <span className="text-muted">{f.label}: </span>
              <span className="font-medium">{String(f.value)}</span>
            </div>
          ))}
        </div>
      )}
      {numbers.length > 0 && (
        <div className="grid grid-cols-2 gap-2 xl:grid-cols-3">
          {numbers.map((f) => (
            <div key={f.name} className="rounded-xl border border-border px-3 py-2" data-testid={`result-${f.name}`}>
              <div className="truncate text-xs text-muted" title={f.label}>{f.label}</div>
              <div className="font-mono text-base font-semibold">
                {show(f.value, f.unit, units)}
                {f.unit && <span className="ml-1 text-xs font-normal text-muted">{displayUnit(f.unit, units)}</span>}
              </div>
            </div>
          ))}
        </div>
      )}

      {columns && rows && (
        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-semibold">Table</span>
            <button className="btn-ghost text-xs" onClick={() => download(`${toolId}.csv`, csv(columns, rows), "text/csv")}>
              <Download className="h-3.5 w-3.5" /> CSV
            </button>
          </div>
          <div className="max-h-96 overflow-auto rounded-xl border border-border">
            <table className="w-full text-right font-mono text-xs">
              <thead className="sticky top-0 bg-bg text-muted">
                <tr>{columns.map((c) => <th key={c} className="whitespace-nowrap px-3 py-2 font-medium">{c}</th>)}</tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i} className="border-t border-border">
                    {r.map((v, j) => <td key={j} className="px-3 py-1.5">{formatNumber(v, 5)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {nestedLists.map((f) => {
        const list = f.value as Record<string, unknown>[];
        const keys = Object.keys(list[0]);
        return (
          <div key={f.name}>
            <div className="mb-2 text-sm font-semibold">{f.label}</div>
            <div className="overflow-auto rounded-xl border border-border">
              <table className="w-full text-right font-mono text-xs">
                <thead className="bg-bg text-muted">
                  <tr>
                    {keys.map((k) => (
                      <th key={k} className="px-3 py-2 font-medium">
                        {k}{NESTED_UNITS[k] ? ` [${displayUnit(NESTED_UNITS[k], units)}]` : ""}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {list.map((row, i) => (
                    <tr key={i} className="border-t border-border">
                      {keys.map((k) => <td key={k} className="px-3 py-1.5">{show(row[k], NESTED_UNITS[k] ?? "", units)}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}
    </div>
  );
}
