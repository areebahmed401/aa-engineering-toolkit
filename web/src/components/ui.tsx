import { clsx, type ClassValue } from "clsx";
import { BatteryCharging, Building2, Flame, Gauge, Loader2, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const SECTION_META: Record<string, { icon: LucideIcon; color: string; text: string; blurb: string }> = {
  thermo: { icon: Flame, color: "bg-thermo", text: "text-thermo", blurb: "Fluid properties, steam tables, pipe pressure drop, insulation, cycles" },
  structural: { icon: Building2, color: "bg-structural", text: "text-structural", blurb: "Section properties, beams with equilibrium or FEM, torsion" },
  electrical: { icon: BatteryCharging, color: "bg-electrical", text: "text-electrical", blurb: "Battery modelling: equivalent circuit, thermal, aging" },
  asme: { icon: Gauge, color: "bg-asme", text: "text-asme", blurb: "ASME VIII Div 1 pressure vessel sizing" },
};

export function Badge({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full border border-border px-2 py-0.5 text-xs text-muted", className)}>
      {children}
    </span>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("h-4 w-4 animate-spin", className)} />;
}

export function SectionDot({ section }: { section: string }) {
  return <span className={cn("inline-block h-2 w-2 rounded-full", SECTION_META[section]?.color ?? "bg-muted")} />;
}
