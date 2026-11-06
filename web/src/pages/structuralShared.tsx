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
