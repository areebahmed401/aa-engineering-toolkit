// Helpers shared by the structural page and its tabs: unit conversions and the card / error box layout bits.
import { TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";
import type { Conversion } from "../components/NumberInput";
import { cn } from "../components/ui";
import { displayUnit, toDisplay, toSI, type UnitSystem } from "../lib/units";

export function unitConv(siUnit: string, system: UnitSystem): Conversion {
  return { unit: displayUnit(siUnit, system), toSI: (v) => toSI(v, siUnit, system), fromSI: (v) => toDisplay(v, siUnit, system) };
}

/** Section dimensions read better in mm / in than in m / ft. */
export function smallLength(system: UnitSystem): Conversion {
  const f = system === "SI" ? 1e-3 : 0.0254;
  return { unit: system === "SI" ? "mm" : "in", toSI: (v) => v * f, fromSI: (v) => v / f };
}

export function stressConv(system: UnitSystem): Conversion {
  const f = system === "SI" ? 1e6 : 6.894757293168e6;
  return { unit: system === "SI" ? "MPa" : "ksi", toSI: (v) => v * f, fromSI: (v) => v / f };
}

export function Card({ title, children, className, aside }: { title: string; children: ReactNode; className?: string; aside?: ReactNode }) {
  return (
    <section className={cn("card p-5", className)}>
      <div className="mb-4 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div className="flex gap-2 rounded-xl border border-fail/30 bg-fail/5 p-3 text-sm text-fail" data-testid="run-error">
      <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
      <span>{message}</span>
    </div>
  );
}

const lin = (unit: string, f: number): Conversion => ({ unit, toSI: (v) => v * f, fromSI: (v) => v / f });
const FT = 0.3048;

/** Section quantities of dimension m^n (J_T m⁴, W_T m³, C_T m⁶, ω m²) in mm^n / in^n. */
export function lengthPowConv(n: 2 | 3 | 4 | 6, system: UnitSystem): Conversion {
  const sup = { 2: "²", 3: "³", 4: "⁴", 6: "⁶" }[n];
  const f = system === "SI" ? 1e-3 : 0.0254;
  return lin(`${system === "SI" ? "mm" : "in"}${sup}`, f ** n);
}

/** Torque in N·m (lbf·ft), not the kN·m of the generic table: torsion loads are small. */
export const torqueConv = (system: UnitSystem): Conversion => (system === "SI" ? lin("N·m", 1) : lin("lbf·ft", 1.355817948));
/** Distributed torque N·m/m (lbf·ft/ft). */
export const torquePerLengthConv = (system: UnitSystem): Conversion => (system === "SI" ? lin("N·m/m", 1) : lin("lbf·ft/ft", 1.355817948 / FT));
/** Bimoment N·m² (lbf·ft²). */
export const bimomentConv = (system: UnitSystem): Conversion => (system === "SI" ? lin("N·m²", 1) : lin("lbf·ft²", 1.355817948 * FT));
export const forceNConv = (system: UnitSystem): Conversion => (system === "SI" ? lin("N", 1) : lin("lbf", 4.448221615));

/** Small segmented switch (same look on every structural tab). */
export function Toggle<T extends string>({ label, value, options, onChange, testId }: {
  label: string; value: T; options: { value: T; label: string; title?: string }[]; onChange: (v: T) => void; testId: string;
}) {
  return (
    <div className="inline-flex rounded-lg border border-border p-0.5 text-xs" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} type="button" aria-pressed={value === o.value} data-testid={`${testId}-${o.value}`} title={o.title}
          className={cn("rounded-md px-2.5 py-1 transition", value === o.value ? "bg-primary text-on-primary" : "text-muted hover:text-ink")}
          onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}
