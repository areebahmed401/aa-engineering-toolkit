// Sidebar navigation: ordered sub-groups per section, resolved against the tool schema and filtered by search.
import type { ToolSchema } from "./types";

type Link = { key: string; label: string; to: string; toolId: string };
type ItemConfig = string | Link;
type GroupConfig = { label: string; items: ItemConfig[] };

const structural = (tab: string, label: string, toolId: string): Link => ({ key: `structural-${tab}`, label, to: `/structural?tab=${tab}`, toolId });

export const NAV: Record<string, GroupConfig[]> = {
  thermo: [
    { label: "Properties & tables", items: ["thermo.fluid_properties", "thermo.saturated_steam_table"] },
    { label: "Piping & heat loss", items: ["thermo.pipe_pressure_drop", "thermo.insulation_thickness", "thermo.insulation_heat_loss"] },
    { label: "Cycles & equipment", items: ["thermo.refrigeration_cycle", "thermo.cooling_tower"] },
  ],
  structural: [
    {
      label: "Structural designer",
      items: [
        structural("section", "1 · Section", "structural.section_properties"),
        structural("beam", "2 · Beam", "structural.beam_analysis"),
        structural("torsion", "3 · Torsion", "structural.torsion"),
        structural("poles", "4 · Pole plan", "structural.pole_plan"),
      ],
    },
  ],
  asme: [
    { label: "Vessel builder", items: ["asme.vessel_design"] },
    { label: "Components", items: ["asme.cylindrical_shell", "asme.spherical_shell", "asme.formed_head", "asme.flat_head", "asme.nozzle_reinforcement"] },
    { label: "Checks", items: ["asme.external_pressure", "asme.hydrotest"] },
  ],
  electrical: [
    { label: "Battery", items: ["electrical.battery_simulator", "electrical.cooling_comparison", "electrical.cycle_life"] },
    { label: "Validation", items: ["electrical.pybamm_reference"] },
  ],
};

export type NavItem = { key: string; label: string; to: string };
export type NavGroup = { label: string; items: NavItem[] };
export type NavSection = { groups: NavGroup[]; count: number };

const matches = (t: ToolSchema, q: string) => !q || `${t.name} ${t.description} ${t.tags.join(" ")}`.toLowerCase().includes(q);

/** Resolve NAV against the schema's tools; `query` filters by name/description/tags. Sections without matching tools are omitted. */
export function buildNav(tools: ToolSchema[], query: string): Record<string, NavSection> {
  const q = query.trim().toLowerCase();
  const byId = new Map(tools.map((t) => [t.id, t]));
  const sectionIds = [...new Set([...Object.keys(NAV), ...tools.map((t) => t.section)])];
  const out: Record<string, NavSection> = {};
  for (const section of sectionIds) {
    const used = new Set<string>();
    const groups: NavGroup[] = [];
    for (const g of NAV[section] ?? []) {
      const items: NavItem[] = [];
      for (const it of g.items) {
        const toolId = typeof it === "string" ? it : it.toolId;
        const tool = byId.get(toolId);
        if (!tool) continue;
        used.add(toolId);
        if (!matches(tool, q)) continue;
        items.push(typeof it === "string" ? { key: tool.id, label: tool.name, to: `/tool/${tool.id}` } : { key: it.key, label: it.label, to: it.to });
      }
      if (items.length) groups.push({ label: g.label, items });
    }
    const other = tools
      .filter((t) => t.section === section && !used.has(t.id) && matches(t, q))
      .map((t) => ({ key: t.id, label: t.name, to: `/tool/${t.id}` }));
    if (other.length) groups.push({ label: "Other", items: other });
    if (groups.length) out[section] = { groups, count: groups.reduce((n, g) => n + g.items.length, 0) };
  }
  return out;
}
