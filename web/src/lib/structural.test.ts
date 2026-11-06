import { describe, expect, it } from "vitest";
import {
  addNode, addWall, BEAM_TOOL, beamInputs, cleanNoise, componentCount, declutter, defaultState, deleteNode, deleteWall, determinacy,
  fbdLayout, fitSection, flowDirection, flowLabelCandidates, flowPoint, flowRegions, flowScale, fromToolInputs, hasWall, leftNormal,
  loadErrors, makeView, maxAbs, mergeState, momentArc, moveNode, nextFreeWall, nodeNear, parseShearResult, SECTION_TOOL, sectionInputs,
  seriesValues, shapeMeta, SHEAR_PRESETS, SHEAR_TOOL, shearError, shearInputs, shearPreset, snapPoint, snapTo, stateDiff, stressAt,
  TORSION_TOOL, torsionError, torsionInputs, wallNear, wallStrokePx, type BeamValues, type FbdFormat, type ShearGeometry,
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

  it("keeps old section/beam URLs decoding the same and adds torsion defaults", () => {
    expect(defaults.torsion).toEqual({ length: 1, torque: 200, position: 1 });
    expect(mergeState(defaults, { section: { width: 0.2 }, beam: { length: 6 } })).toEqual({
      ...defaults, section: { ...defaults.section, width: 0.2 }, beam: { ...defaults.beam, length: 6 },
    });
  });

  it("round-trips torsion values and builds torsion inputs", () => {
    const changed = { ...defaults, material: "Aluminium 6061-T6", torsion: { length: 2, torque: 500, position: 1.5 } };
    const diff = stateDiff(changed, defaults);
    expect(diff).toEqual({ material: "Aluminium 6061-T6", torsion: { length: 2, torque: 500, position: 1.5 } });
    expect(mergeState(defaults, diff)).toEqual(changed);
    expect(torsionInputs(changed)).toEqual({
      section: defaults.section, material: "Aluminium 6061-T6", length: 2, torque: 500, position: 1.5,
    });
    const custom = defaultState(sectionDefaults, beamDefaults, { section: {}, material: "Steel", length: 3, torque: 10, position: 3 });
    expect(custom.torsion).toEqual({ length: 3, torque: 10, position: 3 });
  });

  it("converts old torsion links", () => {
    expect(fromToolInputs(TORSION_TOOL, { section: { shape: "c_beam" }, material: "Steel", length: 2, torque: 50 }))
      .toEqual({ section: { shape: "c_beam" }, material: "Steel", torsion: { length: 2, torque: 50 } });
    expect(fromToolInputs(TORSION_TOOL, {})).toEqual({});
  });

  it("requires the torsion position to lie within the length", () => {
    expect(torsionError({ length: 2, torque: 1, position: 2 })).toBeNull();
    expect(torsionError({ length: 2, torque: 1, position: 2.5 })).toMatch(/within/);
    expect(torsionError({ length: 0, torque: 1, position: 0 })).toMatch(/positive/);
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

describe("stressAt", () => {
  const xs = [0, 1, 3];
  const top = [10, 20, -20];
  const bottom = [-10, -20, 20];
  it("returns the end values at and beyond the ends", () => {
    expect(stressAt(0, xs, top, bottom)).toEqual({ top: 10, bottom: -10 });
    expect(stressAt(-1, xs, top, bottom)).toEqual({ top: 10, bottom: -10 });
    expect(stressAt(3, xs, top, bottom)).toEqual({ top: -20, bottom: 20 });
    expect(stressAt(9, xs, top, bottom)).toEqual({ top: -20, bottom: 20 });
  });
  it("interpolates linearly between stations and keeps signs opposite", () => {
    expect(stressAt(0.5, xs, top, bottom)).toEqual({ top: 15, bottom: -15 });
    const m = stressAt(2, xs, top, bottom);
    expect(m.top).toBeCloseTo(0);
    expect(m.bottom).toBeCloseTo(0);
    expect(stressAt(2.5, xs, top, bottom).top).toBeLessThan(0);
  });
  it("copes with empty input", () => {
    expect(stressAt(1, [], [], []).top).toBeNaN();
  });
});

describe("shear flow: state and presets", () => {
  const sectionDefaults = { shape: "i_beam", material: "Steel" };
  const beamDefaults = { section: { shape: "i_beam" }, material: "Steel", ...beam() };
  const defaults = defaultState(sectionDefaults, beamDefaults);

  it("defaults to the Python channel and builds the tool inputs unchanged", () => {
    expect(defaults.shear.nodes).toEqual([{ x2: 0.05, x3: 0 }, { x2: 0, x3: 0 }, { x2: 0, x3: 0.1 }, { x2: 0.05, x3: 0.1 }]);
    expect(defaults.shear.walls).toEqual([{ i: 0, j: 1, h: 0.002, G: 81e9 }, { i: 1, j: 2, h: 0.002, G: 81e9 }, { i: 2, j: 3, h: 0.002, G: 81e9 }]);
    expect(shearInputs(defaults)).toEqual(defaults.shear);
    expect(defaults.shear).toMatchObject({ Q2: 0, Q3: 1000, Mt: 0, load_at_shear_centre: true });
  });

  it("round-trips shear changes through the share link and old tool links", () => {
    const box = shearPreset("closed_box");
    const changed = { ...defaults, shear: { ...defaults.shear, Q3: 500, load_at_shear_centre: false, a2: 0.02, walls: box.walls, nodes: box.nodes } };
    const diff = stateDiff(changed, defaults);
    expect(Object.keys(diff)).toEqual(["shear"]);
    expect(Object.keys(diff.shear as object).sort()).toEqual(["Q3", "a2", "load_at_shear_centre", "nodes", "walls"]);
    expect(mergeState(defaults, JSON.parse(JSON.stringify(diff)))).toEqual(changed);
    expect(stateDiff(defaults, defaults)).toEqual({});
    expect(fromToolInputs(SHEAR_TOOL, { Q3: 5 })).toEqual({ shear: { Q3: 5 } });
    expect(fromToolInputs(SHEAR_TOOL, {})).toEqual({});
  });

  it("presets are valid sections of the right topology and size", () => {
    for (const p of SHEAR_PRESETS) {
      const g = shearPreset(p.id);
      expect(shearError(g), p.id).toBeNull();
      const cells = g.walls.length - g.nodes.length + 1;
      expect(cells, p.id).toBe({ closed_box: 1, closed_tube: 1, two_cell_box: 2 }[p.id] ?? 0);
      const xs = g.nodes.map((n) => n.x2);
      const ys = g.nodes.map((n) => n.x3);
      const ext = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));
      expect(ext, p.id).toBeGreaterThanOrEqual(0.05);
      expect(ext, p.id).toBeLessThanOrEqual(0.2);
      expect(g.walls.every((w) => w.h === 0.002 && w.G === 81e9)).toBe(true);
    }
    expect(shearPreset("slit_tube").walls).toHaveLength(24);
    expect(shearPreset("slit_tube").nodes).toHaveLength(25);
    expect(shearPreset("closed_tube").walls).toHaveLength(24);
  });
});

describe("shear flow: validation and editing", () => {
  const g = (): ShearGeometry => shearPreset("channel");
  const wall = (i: number, j: number, h = 0.002) => ({ i, j, h, G: 81e9 });

  it("reports the problems the tool would reject", () => {
    expect(shearError({ nodes: [{ x2: 0, x3: 0 }], walls: [] })).toMatch(/2 nodes/);
    expect(shearError({ ...g(), walls: [] })).toMatch(/at least one wall/);
    expect(shearError({ ...g(), walls: [wall(1, 1)] })).toMatch(/to itself/);
    expect(shearError({ ...g(), walls: [wall(0, 1), wall(1, 0)] })).toMatch(/duplicates wall 0/);
    expect(shearError({ ...g(), walls: [wall(0, 9)] })).toMatch(/out of range/);
    expect(shearError({ ...g(), walls: [wall(0, 1, 0), wall(1, 2), wall(2, 3)] })).toMatch(/thickness/);
    expect(shearError({ ...g(), walls: [wall(0, 1)] })).toMatch(/not connected/);
    expect(shearError(g())).toBeNull();
  });

  it("counts connected components", () => {
    expect(componentCount(4, [{ i: 0, j: 1 }, { i: 2, j: 3 }])).toBe(2);
    expect(componentCount(4, [{ i: 0, j: 1 }, { i: 1, j: 2 }, { i: 3, j: 2 }])).toBe(1);
  });

  it("snaps, finds nodes and walls, and refuses duplicate walls", () => {
    expect(snapTo(0.0123, 0.005)).toBe(0.01);
    expect(snapTo(0.0126, 0.005)).toBe(0.015);
    expect(snapPoint([0.0049, -0.0026], 0.005)).toEqual([0.005, -0.005]);
    const geo = g();
    expect(nodeNear(geo.nodes, [0.001, 0.001], 0.005)).toBe(1);
    expect(nodeNear(geo.nodes, [0.03, 0.03], 0.005)).toBe(-1);
    expect(wallNear(geo, [0, 0.05], 0.003)).toBe(1);
    expect(wallNear(geo, [0.03, 0.05], 0.003)).toBe(-1);
    expect(addWall(geo, 0, 1, 0.002)).toBe(geo);
    expect(addWall(geo, 1, 0, 0.002)).toBe(geo);
    expect(addWall(geo, 2, 2, 0.002)).toBe(geo);
    expect(addWall(geo, 0, 3, 0.003).walls[3]).toEqual({ i: 0, j: 3, h: 0.003, G: 81e9 });
    expect(hasWall(geo, 3, 2)).toBe(true);
    expect(nextFreeWall(geo)).toEqual([0, 2]);
    expect(nextFreeWall({ nodes: [{ x2: 0, x3: 0 }, { x2: 1, x3: 0 }], walls: [wall(0, 1)] })).toBeNull();
  });

  it("deleting a node removes its walls and reindexes the rest", () => {
    const out = deleteNode(g(), 1);
    expect(out.nodes).toHaveLength(3);
    expect(out.walls).toEqual([wall(1, 2)]);
    expect(deleteWall(g(), 0).walls.map((w) => w.i)).toEqual([1, 2]);
    expect(addNode(g(), [0.1, 0.1]).index).toBe(4);
    expect(moveNode(g(), 0, [0.01, 0.02]).nodes[0]).toEqual({ x2: 0.01, x3: 0.02 });
  });
});

describe("shear flow: plot geometry", () => {
  it("left normal follows the screen: a wall pointing right has its left side up (negative x3)", () => {
    expect(leftNormal([0, 0], [1, 0])).toEqual([0, -1]);
    const down = leftNormal([0, 0], [0, 2]);
    expect(down[0]).toBeCloseTo(1);
    expect(down[1]).toBeCloseTo(0);
  });

  it("scales the largest flow to 15 % of the extent", () => {
    expect(flowScale(200, 0.1)).toBeCloseTo(0.015 / 200);
    expect(flowScale(0, 0.1)).toBe(0);
  });

  it("offsets the flow curve by k·t along the normal and splits the fill at sign changes", () => {
    const x2 = [0, 1, 2, 3, 4];
    const x3 = [0, 0, 0, 0, 0];
    const same = flowRegions(x2, x3, [0, 1, 2, 1, 0], 0.1);
    expect(same).toHaveLength(1);
    expect(same[0].positive).toBe(true);
    expect(Math.min(...same[0].points.map((p) => p[1]))).toBeCloseTo(-0.2); // left of +x2 is up
    const split = flowRegions(x2, x3, [-1, -1, 0, 1, 1], 0.1);
    expect(split.map((r) => r.positive)).toEqual([false, true]);
    expect(flowRegions(x2, x3, [1, 1, 1, 1, 1], 0)).toEqual([]);
    expect(flowPoint(x2, x3, [0, 0, 2, 0, 0], 0.1, 2)).toEqual([2, -0.2]);
    // a sign change between samples is split at the zero crossing
    const cross = flowRegions([0, 2], [0, 0], [1, -1], 0.1);
    expect(cross.map((r) => r.positive)).toEqual([true, false]);
    expect(cross[0].points.some((p) => Math.abs(p[0] - 1) < 1e-12 && p[1] === 0)).toBe(true);
  });

  it("arrows follow the sign of t times the wall direction", () => {
    expect(flowDirection([0, 0], [2, 0], 5)).toEqual([1, 0]);
    expect(flowDirection([0, 0], [2, 0], -5)).toEqual([-1, 0]);
    expect(flowDirection([0, 0], [0, 3], -1)[1]).toBe(-1);
  });

  it("labels the extreme and the ends, skipping values under 5 % of the maximum", () => {
    const c = flowLabelCandidates([[0, 1, 2, 1, 0], [-100, -50, 1, 30, 100]], 100);
    expect(c.map((x) => [x.wall, x.index, x.priority])).toEqual([[1, 0, 1], [1, 4, 1]]);
    const w = flowLabelCandidates([[0, 40, 90, 40, 0]], 100);
    expect(w.map((x) => [x.index, x.priority])).toEqual([[2, 0]]);
  });

  it("declutter keeps the first of any two labels that are too close", () => {
    const kept = declutter([{ x: 0, y: 0, id: "a" }, { x: 10, y: 0, id: "b" }, { x: 50, y: 0, id: "c" }], 30);
    expect(kept.map((k) => k.id)).toEqual(["a", "c"]);
  });

  it("view maps the points into the box and back, x3 pointing down", () => {
    const view = makeView([[0, 0], [0.2, 0.1]], 400, 300, 20);
    const [x, y] = view.toPx([0.1, 0.05]);
    expect(x).toBeCloseTo(200);
    expect(y).toBeCloseTo(150);
    const [a, b] = view.toWorld(view.toPx([0.03, 0.07]));
    expect(a).toBeCloseTo(0.03);
    expect(b).toBeCloseTo(0.07);
    expect(view.toPx([0.2, 0.1])[1]).toBeGreaterThan(view.toPx([0, 0])[1]);
    expect(wallStrokePx(0.002, 1000)).toBe(1.5);
    expect(wallStrokePx(0.002, 10000)).toBe(8);
  });

  it("cleans float noise and parses the tool result", () => {
    expect(cleanNoise(1e-20, 1)).toBe(0);
    expect(Object.is(cleanNoise(-0, 1), 0)).toBe(true);
    expect(cleanNoise(3, 1)).toBe(3);
    const wall = { wall: 0, i: 0, j: 1, h: 0.002, G: 81e9, length: 1, s: [0, 1], x2: [0, 1], x3: [0, 0],
      t_cut: [0, 4], t0: [1, 1], t_torque: [0, 0], t_total: [1, 5], tau: [500, 2500] };
    const r = parseShearResult([
      { name: "walls", value: [wall] }, { name: "steps", value: [{ label: "J22", value: 2, unit: "m^4" }] },
      { name: "A", value: 3 }, { name: "tau_torsion_open", value: null }, { name: "note", value: "x" }, { name: "cut_walls", value: [0] },
    ])!;
    expect(r.A).toBe(3);
    expect(r.tau_torsion_open).toBeNaN();
    expect(r.cut_walls).toEqual([0]);
    expect(r.steps[0].unit).toBe("m^4");
    expect(parseShearResult([{ name: "A", value: 1 }])).toBeNull();
    expect(seriesValues(r.walls, "t_total", "t")).toEqual([[1, 5]]);
    expect(seriesValues(r.walls, "t_total", "tau")).toEqual([[500, 2500]]);
    expect(maxAbs(seriesValues(r.walls, "t_cut", "t"))).toBe(4);
  });
});
