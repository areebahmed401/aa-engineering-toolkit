import { describe, expect, it } from "vitest";
import {
  BEAM_TOOL, beamInputs, defaultState, determinacy, fbdLayout, fitSection, fromToolInputs, loadErrors, mergeState,
  momentArc, SECTION_TOOL, sectionInputs, shapeMeta, stateDiff, type BeamValues, type FbdFormat,
} from "./structural";
import type { ToolSchema } from "./types";

const fmt: FbdFormat = { force: (n) => `${n} N`, udl: (n) => `${n} N/m`, moment: (n) => `${n} N·m`, length: (n) => `${n} m` };
const beam = (p: Partial<BeamValues> = {}): BeamValues => ({
  length: 4, left_support: "fixed", right_support: "pinned", theory: "EB", n_elem: 200,
  loads: [{ kind: "point", value: 10e3, x: 2, x_end: null }], ...p,
});

describe("determinacy", () => {
  it("matches static_determinacy for every support pair", () => {
    expect(determinacy("fixed", "free")).toMatchObject({ degree: 0, status: "determinate" });
    expect(determinacy("pinned", "roller")).toMatchObject({ degree: 0, status: "determinate" });
    expect(determinacy("fixed", "pinned")).toMatchObject({ degree: 1, status: "indeterminate" });
    expect(determinacy("fixed", "fixed")).toMatchObject({ degree: 2, status: "indeterminate" });
    expect(determinacy("pinned", "free")).toMatchObject({ degree: -1, status: "mechanism" });
    expect(determinacy("free", "free")).toMatchObject({ degree: -2, status: "mechanism" });
  });

  it("names the method the Python side will use", () => {
    expect(determinacy("pinned", "pinned").method).toMatch(/Equilibrium/);
    expect(determinacy("pinned", "pinned", "TB").method).toMatch(/Timoshenko/);
    expect(determinacy("fixed", "pinned").method).toMatch(/FEM/);
  });
});

describe("loads", () => {
  it("flags positions outside the span", () => {
    const b = beam({ loads: [
      { kind: "point", value: 1, x: 5, x_end: null },
      { kind: "udl", value: 1, x: 1, x_end: 0.5 },
      { kind: "udl", value: 1, x: 1, x_end: null },
    ] });
    expect(Object.keys(loadErrors(b))).toEqual(["0", "1"]);
  });
});

describe("state", () => {
  const sectionDefaults = { shape: "i_beam", width: 0.1, material: "Steel" };
  const beamDefaults = { section: { shape: "i_beam", width: 0.1 }, material: "Steel", ...beam() };
  const defaults = defaultState(sectionDefaults, beamDefaults);

  it("builds tool inputs from the shared state", () => {
    expect(sectionInputs(defaults)).toEqual({ shape: "i_beam", width: 0.1, material: "Steel" });
    expect(beamInputs(defaults)).toMatchObject({ section: { shape: "i_beam" }, material: "Steel", length: 4, left_support: "fixed" });
  });

  it("encodes only changes and merges them back", () => {
    const changed = { ...defaults, section: { ...defaults.section, width: 0.2 }, beam: { ...defaults.beam, length: 6 } };
    const diff = stateDiff(changed, defaults);
    expect(diff).toEqual({ section: { width: 0.2 }, beam: { length: 6 } });
    expect(mergeState(defaults, diff)).toEqual(changed);
    expect(stateDiff(defaults, defaults)).toEqual({});
  });

  it("converts old tool links", () => {
    expect(fromToolInputs(SECTION_TOOL, { shape: "circle", material: "Aluminium 6061-T6" }))
      .toEqual({ section: { shape: "circle" }, material: "Aluminium 6061-T6" });
    expect(fromToolInputs(BEAM_TOOL, { length: 3, section: { shape: "rectangle" } }))
      .toEqual({ section: { shape: "rectangle" }, beam: { length: 3 } });
    expect(fromToolInputs(BEAM_TOOL, {})).toEqual({});
  });

  it("reads shape fields from the schema hint", () => {
    const fields = { rectangle: [["width", "Width b"], ["height", "Height h"]], circle: [["radius", "Radius r"]] };
    const tool = { inputs: { properties: { shape: { enum: ["rectangle", "circle"], shape_fields: fields, shape_labels: { circle: "Circle" } } } } } as unknown as ToolSchema;
    expect(shapeMeta(tool)).toEqual({ shapes: ["rectangle", "circle"], fields, labels: { circle: "Circle" } });
    expect(shapeMeta(undefined)).toEqual({ shapes: [], fields: {}, labels: {} });
  });
});

describe("fbdLayout", () => {
  it("places loads along the beam and points arrows by sign", () => {
    const f = fbdLayout(beam({ loads: [
      { kind: "point", value: 10e3, x: 2, x_end: null },
      { kind: "point", value: -5e3, x: 4, x_end: null },
      { kind: "udl", value: 2e3, x: 0, x_end: 2 },
      { kind: "moment", value: -3e3, x: 1, x_end: null },
    ] }), fmt);
    const mid = (f.x0 + f.x1) / 2;
    expect(f.points[0].x).toBeCloseTo(mid);
    expect(f.points[0].yHead).toBeGreaterThan(f.points[0].yTail); // downward
    expect(f.points[1].yHead).toBeLessThan(f.points[1].yTail); // upward
    // the smaller load gets the shorter arrow
    expect(Math.abs(f.points[1].yHead - f.points[1].yTail)).toBeLessThan(Math.abs(f.points[0].yHead - f.points[0].yTail));
    expect(f.udls[0]).toMatchObject({ x1: f.x0, down: true });
    expect(f.udls[0].x2).toBeCloseTo(mid);
    expect(f.udls[0].arrows.length).toBeGreaterThan(2);
    expect(f.moments[0]).toMatchObject({ ccw: false, label: "3000 N·m" });
    expect(f.ticks.map((t) => t.label)).toEqual(["0 m", "1 m", "2 m", "4 m"]);
    expect(f.supports.map((s) => s.kind)).toEqual(["fixed", "pinned"]);
  });

  it("UDL with no end runs to the beam end; zero loads are skipped", () => {
    const f = fbdLayout(beam({ loads: [{ kind: "udl", value: 1, x: 1, x_end: null }, { kind: "point", value: 0, x: 1, x_end: null }] }), fmt);
    expect(f.udls[0].x2).toBe(f.x1);
    expect(f.points).toHaveLength(0);
  });

  it("draws reactions (up +) only once they are known", () => {
    expect(fbdLayout(beam(), fmt).reactions).toHaveLength(0);
    const f = fbdLayout(beam(), fmt, { Ay: 6875, MA: 3750, By: 3125, MB: null });
    expect(f.reactions).toHaveLength(2);
    expect(f.reactions.every((r) => r.yHead < r.yTail)).toBe(true);
    expect(f.reactions.map((r) => r.label)).toEqual(["6875 N", "3125 N"]);
    expect(f.reactionMoments).toEqual([expect.objectContaining({ x: f.x0, ccw: true })]);
  });
});

describe("geometry helpers", () => {
  it("momentArc ends where the arrowhead starts", () => {
    for (const ccw of [true, false]) {
      const { d, head } = momentArc(100, 100, 20, ccw);
      const [, ex, ey] = d.match(/ ([\d.]+) ([\d.]+)$/)!.map(Number);
      const dist = Math.hypot(head[1][0] - ex, head[1][1] - ey);
      expect(dist).toBeLessThan(10);
      expect(Math.hypot(ex - 100, ey - 100)).toBeCloseTo(20, 1);
    }
  });

  it("fitSection keeps the aspect ratio and flips y", () => {
    const { map } = fitSection([[[0, 0], [0.1, 0], [0.1, 0.2], [0, 0.2]]], 200, 200, 10);
    const [x0, y0] = map([0, 0]);
    const [x1, y1] = map([0.1, 0.2]);
    expect(y1).toBeLessThan(y0);
    expect((y0 - y1) / (x1 - x0)).toBeCloseTo(2);
  });
});
