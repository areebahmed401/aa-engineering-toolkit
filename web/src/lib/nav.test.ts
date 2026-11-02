import { describe, expect, it } from "vitest";
import { buildNav } from "./nav";
import type { ToolSchema } from "./types";

const tool = (id: string, name = id, description = "", tags: string[] = []): ToolSchema => ({
  id, name, section: id.split(".")[0], description, reference: "", tags, custom_page: false, has_charts: false, inputs: {},
});

const tools = [
  tool("thermo.cooling_tower", "Cooling tower"),
  tool("thermo.fluid_properties", "Fluid properties", "", ["coolprop"]),
  tool("thermo.new_thing", "New thing"),
  tool("structural.torsion", "Torsion", "Warping of thin-walled sections"),
  tool("structural.beam_analysis", "Beam analysis", "Deflection and moment"),
  tool("structural.section_properties", "Section properties", "Area and inertia"),
];

describe("buildNav", () => {
  it("orders groups and items by config, skipping missing ids", () => {
    const nav = buildNav(tools, "");
    expect(nav.thermo.groups.map((g) => g.label)).toEqual(["Properties & tables", "Cycles & equipment", "Other"]);
    expect(nav.thermo.groups[0].items.map((i) => i.key)).toEqual(["thermo.fluid_properties"]);
  });

  it("puts unconfigured tools in Other", () => {
    const nav = buildNav(tools, "");
    expect(nav.thermo.groups.at(-1)).toEqual({ label: "Other", items: [{ key: "thermo.new_thing", label: "New thing", to: "/tool/thermo.new_thing" }] });
    expect(nav.thermo.count).toBe(3);
  });

  it("maps structural tools to tab links, in order, with no Other group", () => {
    const g = buildNav(tools, "").structural.groups;
    expect(g).toHaveLength(1);
    expect(g[0].items.map((i) => [i.label, i.to])).toEqual([
      ["1 · Section", "/structural?tab=section"],
      ["2 · Beam", "/structural?tab=beam"],
      ["3 · Torsion", "/structural?tab=torsion"],
    ]);
  });

  it("filters by name, description and tags, dropping empty groups and sections", () => {
    expect(buildNav(tools, "coolprop").thermo.groups.map((g) => g.label)).toEqual(["Properties & tables"]);
    const nav = buildNav(tools, "tower");
    expect(nav.thermo.count).toBe(1);
    expect(nav.structural).toBeUndefined();
  });

  it("matches structural links against their tool text", () => {
    expect(buildNav(tools, "beam").structural.groups[0].items.map((i) => i.label)).toEqual(["2 · Beam"]);
    expect(buildNav(tools, "warping").structural.groups[0].items.map((i) => i.label)).toEqual(["3 · Torsion"]);
    expect(buildNav(tools, "inertia").structural.groups[0].items.map((i) => i.label)).toEqual(["1 · Section"]);
    expect(buildNav(tools, "BEAM").structural.count).toBe(1);
  });
});
