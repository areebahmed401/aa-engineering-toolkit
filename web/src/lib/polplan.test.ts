import { describe, expect, it } from "vitest";
import {
  addMember, addNode, bestLabelSpot, clipLine, clusterOffsets, contradictionPoint, displacedSegments, displacementFactor, emptyHistory, EMPTY_MODEL,
  fitView, hitTest, labelClearance, moveNode, nodeAt, nodeById, normalizeModel, panBy, parsePoleResult, pickNode, placeInfinityPoles, POLE_PRESETS, poleReportExtra,
  poleText, rayToEdge, record, redo, removeMember, removeNode, removeSupport, rotateSupport, setSupport, setSupportAngle, snap, snapPoint,
  splitMember, supportSide, toggleJoint, toModel, toolInputs, toScreen, undo, zoomAt, type PoleModel, type PoleResult, type View,
} from "./polplan";
import { decodeInputs, encodeInputs } from "./urlState";
import { defaultState, fromToolInputs, mergeState, POLE_TOOL, polesInputs, stateDiff } from "./structural";

const beam: PoleModel = {
  nodes: [{ id: "A", x: 0, y: 0, joint: "rigid" }, { id: "B", x: 4, y: 0, joint: "hinge" }, { id: "C", x: 8, y: 0, joint: "rigid" }],
  members: [{ id: "m1", a: "A", b: "B" }, { id: "m2", a: "B", b: "C" }],
  supports: [{ node: "A", kind: "pin", angle: 0 }, { node: "C", kind: "roller", angle: 0 }],
};

describe("snapping and view", () => {
  it("snaps to the grid step and avoids -0 and float noise", () => {
    expect(snap(1.4, 1)).toBe(1);
    expect(snap(1.6, 1)).toBe(2);
    expect(snap(0.74, 0.5)).toBe(0.5);
    expect(snap(0.8, 0.5)).toBe(1);
    expect(snap(2.9, 2)).toBe(2);
    expect(Object.is(snap(-0.2, 1), 0)).toBe(true);
    expect(snap(0.1 + 0.2 + 0.7, 0.1)).toBe(1);
    expect(snapPoint([3.3, -4.6], 1)).toEqual([3, -5]);
  });

  it("converts between screen and model coordinates (y up) and zooms about the cursor", () => {
    const v: View = { cx: 5, cy: 2, scale: 40 };
    expect(toScreen(v, 800, 400, [5, 2])).toEqual([400, 200]);
    expect(toScreen(v, 800, 400, [6, 3])).toEqual([440, 160]);
    expect(toModel(v, 800, 400, [440, 160])).toEqual([6, 3]);
    const z = zoomAt(v, 800, 400, [440, 160], 2);
    expect(z.scale).toBe(80);
    const [sx, sy] = toScreen(z, 800, 400, [6, 3]);
    expect(sx).toBeCloseTo(440);
    expect(sy).toBeCloseTo(160);
    expect(zoomAt(v, 800, 400, [0, 0], 1e6).scale).toBeLessThanOrEqual(600);
    const p = panBy(v, 40, -40);
    expect(p.cx).toBeCloseTo(4);
    expect(p.cy).toBeCloseTo(1); // dragging up moves the view centre down
  });

  it("fits the drawing into the canvas", () => {
    const v = fitView(beam, 800, 400, 40);
    expect(v.cx).toBe(4);
    expect(v.scale).toBeCloseTo(720 / 8);
    expect(toScreen(v, 800, 400, [0, 0])[0]).toBeCloseTo(40);
  });
});

describe("hit testing", () => {
  it("finds the nearest node within the tolerance", () => {
    expect(nodeAt(beam, [3.9, 0.1], 0.3)?.id).toBe("B");
    expect(nodeAt(beam, [2, 1], 0.3)).toBeNull();
  });

  it("prefers nodes, then support symbols, then members", () => {
    expect(hitTest(beam, [4.05, 0.05], 0.2, 0.6)).toEqual({ kind: "node", id: "B" });
    expect(hitTest(beam, [0, -0.4], 0.2, 0.6)).toEqual({ kind: "support", node: "A" }); // pin symbol hangs below the node
    expect(hitTest(beam, [2, 0.1], 0.2, 0.6)).toEqual({ kind: "member", id: "m1" });
    expect(hitTest(beam, [2, 2], 0.2, 0.6)).toBeNull();
  });

  it("puts the support symbol on the side away from the members", () => {
    expect(supportSide(beam, beam.supports[0])).toEqual([0, -1]);
    const col: PoleModel = {
      nodes: [{ id: "A", x: 0, y: 0, joint: "rigid" }, { id: "B", x: 0, y: 3, joint: "rigid" }],
      members: [{ id: "m", a: "A", b: "B" }], supports: [{ node: "A", kind: "roller", angle: 90 }],
    };
    expect(supportSide(col, col.supports[0])).toEqual([1, 0]); // free direction vertical -> ground to the side
    const wall = setSupport(col, "A", "fixed");
    expect(supportSide(wall, wall.supports[0])).toEqual([0, -1]);
  });
});

describe("model edits", () => {
  it("adds nodes and bars with fresh ids and ignores duplicates", () => {
    let m = addNode(EMPTY_MODEL, 0, 0).model;
    const b = addNode(m, 3, 0);
    expect(b.id).toBe("n2");
    m = addMember(b.model, "n1", "n2");
    expect(m.members).toEqual([{ id: "m1", a: "n1", b: "n2" }]);
    expect(addMember(m, "n2", "n1")).toBe(m);
    expect(addMember(m, "n1", "n1")).toBe(m);
    expect(addMember(m, "n1", "zz")).toBe(m);
  });

  it("splits a bar when a node is placed on it", () => {
    const r = splitMember(beam, "m1", [2, 0]);
    expect(r.model.members.map((x) => [x.id, x.a, x.b])).toEqual([["m1", "A", r.id], ["m3", r.id, "B"], ["m2", "B", "C"]]);
    expect(nodeById(r.model, r.id)).toMatchObject({ x: 2, y: 0, joint: "rigid" });
  });

  it("picks an existing node, splits a bar at a grid point or creates a node", () => {
    const opts = { tol: 0.3, step: 1 };
    expect(pickNode(beam, [4.1, 0.1], opts)).toMatchObject({ id: "B", model: beam });
    const split = pickNode(beam, [2.1, 0.15], opts);
    expect(split.model.nodes).toHaveLength(4);
    expect(nodeById(split.model, split.id)).toMatchObject({ x: 2, y: 0 });
    expect(split.model.members).toHaveLength(3);
    const fresh = pickNode(beam, [2.2, 3.1], opts);
    expect(nodeById(fresh.model, fresh.id)).toMatchObject({ x: 2, y: 3 });
    expect(fresh.model.members).toHaveLength(2);
    // an inclined bar is split where it was clicked even when that is off the grid
    const inc = addMember(addNode(addNode(EMPTY_MODEL, 0, 0).model, 3, 1).model, "n1", "n2");
    const hit = pickNode(inc, [1.4, 0.5], { tol: 0.3, step: 1 });
    const n = nodeById(hit.model, hit.id)!;
    expect(n.y / n.x).toBeCloseTo(1 / 3, 3);
  });

  it("toggles joints: the same type again makes the node rigid", () => {
    const m = toggleJoint(beam, "A", "hinge");
    expect(nodeById(m, "A")?.joint).toBe("hinge");
    expect(nodeById(toggleJoint(m, "A", "hinge"), "A")?.joint).toBe("rigid");
    expect(nodeById(toggleJoint(m, "A", "sleeve"), "A")?.joint).toBe("sleeve");
    expect(toggleJoint(beam, "nope", "hinge")).toBe(beam);
  });

  it("places, replaces, rotates and removes supports", () => {
    let m = setSupport(beam, "B", "roller", 90);
    expect(m.supports.find((s) => s.node === "B")).toEqual({ node: "B", kind: "roller", angle: 90 });
    expect(setSupport(m, "B", "roller", 0)).toBe(m); // same kind keeps the angle
    m = setSupport(m, "B", "pin");
    expect(m.supports.find((s) => s.node === "B")).toEqual({ node: "B", kind: "pin", angle: 0 });
    expect(m.supports).toHaveLength(3);
    m = setSupport(beam, "C", "clamp", 90);
    expect(rotateSupport(m, "C", 90).supports.find((s) => s.node === "C")?.angle).toBe(0); // 90 + 90 folds into [0, 180)
    expect(setSupportAngle(m, "C", -45).supports.find((s) => s.node === "C")?.angle).toBe(135);
    expect(setSupportAngle(beam, "A", 30)).toBe(beam); // a pin has no direction
    expect(removeSupport(beam, "A").supports.map((s) => s.node)).toEqual(["C"]);
    expect(removeSupport(beam, "B")).toBe(beam);
  });

  it("moves nodes", () => {
    const m = moveNode(beam, "B", 5, 1);
    expect(nodeById(m, "B")).toMatchObject({ x: 5, y: 1 });
    expect(moveNode(beam, "B", 4, 0)).toBe(beam);
  });

  it("deleting a node removes its members and supports and leaves no orphans", () => {
    const m = removeNode(beam, "A");
    expect(m.nodes.map((n) => n.id)).toEqual(["B", "C"]);
    expect(m.members.map((x) => x.id)).toEqual(["m2"]);
    expect(m.supports.map((s) => s.node)).toEqual(["C"]);
    const mid = removeNode(beam, "B");
    expect(mid.members).toEqual([]);
    expect(mid.nodes).toEqual([]); // A and C lost their only bar
    expect(mid.supports).toEqual([]);
    expect(removeNode(beam, "zz")).toBe(beam);
  });

  it("deleting a bar drops end nodes (and their supports) that no other bar uses", () => {
    const m = removeMember(beam, "m1");
    expect(m.nodes.map((n) => n.id)).toEqual(["B", "C"]);
    expect(m.supports.map((s) => s.node)).toEqual(["C"]);
    expect(removeMember(beam, "zz")).toBe(beam);
  });

  it("sends only connected nodes and their supports to the tool", () => {
    const m = setSupport(addNode(beam, 10, 10).model, "n1", "fixed");
    expect(m.nodes).toHaveLength(4);
    const t = toolInputs(m);
    expect(t.nodes.map((n) => n.id)).toEqual(["A", "B", "C"]);
    expect(t.supports.map((s) => s.node)).toEqual(["A", "C"]);
  });
});

describe("undo / redo", () => {
  it("steps back and forth and drops the redo branch on a new edit", () => {
    let h = emptyHistory<number>();
    h = record(h, 1);
    h = record(h, 2);
    const u1 = undo(h, 3)!;
    expect(u1.value).toBe(2);
    const u2 = undo(u1.history, u1.value)!;
    expect(u2.value).toBe(1);
    expect(undo(u2.history, u2.value)).toBeNull();
    const r = redo(u2.history, u2.value)!;
    expect(r.value).toBe(2);
    expect(r.history.future).toEqual([3]);
    expect(redo(emptyHistory<number>(), 0)).toBeNull();
    expect(record(r.history, 9).future).toEqual([]);
  });

  it("works on whole models", () => {
    const m1 = removeNode(beam, "A");
    const h = record(emptyHistory<PoleModel>(), beam);
    const u = undo(h, m1)!;
    expect(u.value).toBe(beam);
    expect(redo(u.history, u.value)!.value).toBe(m1);
  });
});

describe("URL round trip", () => {
  const defaults = defaultState({ material: "Steel" }, { section: { shape: "i_beam" }, material: "Steel", length: 4 });

  it("starts from the first preset and omits it from the URL", () => {
    expect(defaults.poles).toBe(POLE_PRESETS[0].model);
    expect(stateDiff(defaults, defaults)).toEqual({});
  });

  it("encodes a changed drawing and decodes the same drawing", () => {
    const changed = { ...defaults, poles: POLE_PRESETS[3].model };
    const diff = stateDiff(changed, defaults);
    expect(Object.keys(diff)).toEqual(["poles"]);
    const encoded = encodeInputs(diff, {});
    expect(mergeState(defaults, decodeInputs(encoded)).poles).toEqual(POLE_PRESETS[3].model);
    const custom = { ...defaults, poles: setSupport(EMPTY_MODEL, "x", "pin") };
    expect(mergeState(defaults, decodeInputs(encodeInputs(stateDiff(custom, defaults), {}))).poles).toEqual(EMPTY_MODEL);
  });

  it("falls back to the defaults for garbage and cleans partial models", () => {
    expect(mergeState(defaults, { poles: 5 }).poles).toBe(defaults.poles);
    expect(mergeState(defaults, { poles: { nodes: "x" } }).poles).toBe(defaults.poles);
    const m = normalizeModel({
      nodes: [{ id: "a", x: 0, y: 0 }, { id: "a", x: 1, y: 1 }, { id: "b", x: 2, y: 0, joint: "weird" }, { id: "c", x: "1", y: 0 }],
      members: [{ id: "m", a: "a", b: "b" }, { id: "bad", a: "a", b: "zz" }],
      supports: [{ node: "a", kind: "pin" }, { node: "b", kind: "magic" }, { node: "zz", kind: "pin" }],
    });
    expect(m).toEqual({
      nodes: [{ id: "a", x: 0, y: 0, joint: "rigid" }, { id: "b", x: 2, y: 0, joint: "rigid" }],
      members: [{ id: "m", a: "a", b: "b" }],
      supports: [{ node: "a", kind: "pin", angle: 0 }],
    });
  });

  it("builds tool inputs and converts old tool links", () => {
    expect(polesInputs(defaults)).toEqual(toolInputs(defaults.poles));
    expect(fromToolInputs(POLE_TOOL, {})).toEqual({});
    const values = toolInputs(POLE_PRESETS[2].model) as unknown as Record<string, unknown>;
    expect(mergeState(defaults, fromToolInputs(POLE_TOOL, values)).poles).toEqual(POLE_PRESETS[2].model);
  });

  it("every preset is a clean model", () => {
    for (const p of POLE_PRESETS) {
      expect(normalizeModel(p.model)).toEqual(p.model);
      expect(toolInputs(p.model).nodes).toHaveLength(p.model.nodes.length); // no orphan nodes
      expect(p.model.supports.every((s) => nodeById(p.model, s.node))).toBe(true);
    }
    expect(POLE_PRESETS.map((p) => p.label)).toEqual([
      "Two-hinge continuous beam", "Two-hinge beam on four supports", "Beam with sliding sleeve",
      "Truss: two bands linked by two bars", "Three-hinged arch", "Four-bar linkage",
    ]);
  });
});

describe("overlay geometry", () => {
  const rect = { minX: 0, minY: 0, maxX: 10, maxY: 6 };

  it("clips infinite lines to the view", () => {
    expect(clipLine([2, 3], [1, 0], rect)).toEqual([[0, 3], [10, 3]]);
    const d = clipLine([5, 3], [0, 1], rect)!;
    expect(d[0][1]).toBe(0);
    expect(d[1][1]).toBe(6);
    expect(clipLine([5, 8], [1, 0], rect)).toBeNull();
    const diag = clipLine([0, 0], [1, 1], rect)!;
    expect(diag[1]).toEqual([6, 6]);
  });

  it("places poles at infinity near the edge along their direction", () => {
    expect(rayToEdge([400, 200], [1, 0], 800, 400, 30)).toEqual([770, 200]);
    expect(rayToEdge([400, 200], [0, 1], 800, 400, 30)).toEqual([400, 370]);
    const [x, y] = rayToEdge([400, 200], [1, 1], 800, 400, 30);
    expect(y).toBeCloseTo(370);
    expect(x).toBeCloseTo(570);
  });

  it("flips the model y axis for the screen and moves overlapping marks into the legend", () => {
    const r = placeInfinityPoles(
      [{ name: "(1,2)", direction: [0, 1] }, { name: "(2)", direction: [0, 1] }, { name: "(2,3)", direction: [1, 0] }],
      [400, 200], 800, 400,
    );
    expect(r.marks.map((m) => m.name)).toEqual(["(1,2)", "(2,3)"]);
    expect(r.marks[0].pos[1]).toBeCloseTo(34); // up on screen
    expect(r.marks[0].dir).toEqual([0, -1]);
    expect(r.legend).toEqual([{ name: "(2)", dir: [0, 1] }]);
  });

  it("spreads labels of coincident points on a ring", () => {
    const off = clusterOffsets([[100, 100], [103, 99], [300, 300]]);
    expect(off[0]).toEqual([0, 0]);
    expect(Math.hypot(...off[1])).toBeGreaterThan(15);
    expect(off[2]).toEqual([0, 0]);
  });
});

describe("tool result", () => {
  const field = (name: string, value: unknown) => ({ name, label: name, unit: "", summary: true, value });
  const result: PoleResult = parsePoleResult([
    field("verdict", "Movable → statically unusable (body 1 immovable)"), field("movable", true), field("dof", 1), field("U", 0), field("A", 5), field("z", 4), field("k", 3),
    field("counting", "U = 0"), field("rules_agree", true),
    field("bodies", [{ id: 1, members: ["m1", "m2"], immovable: true, reason: "x", label: [2, 0], merged_into: null }, { id: 2, members: ["m3"], immovable: false, reason: "", label: [8, 0], merged_into: null }]),
    field("poles", [
      { name: "(2)", i: 2, j: 0, x: 7, y: 0, at_infinity: false, direction: null, source: "rule", status: "determined" },
      { name: "(1,2)", i: 1, j: 2, x: null, y: null, at_infinity: true, direction: [0, 1], source: "displacement", status: "determined" },
      { name: "(3)", i: 3, j: 0, x: null, y: null, at_infinity: false, direction: null, source: "rule", status: "line" },
    ]),
    field("loci", []),
    field("contradictions", [{ pole: "(1)", body: 1, bodies: [1], text: "no pole", at: null }]),
    field("steps", ["a", "b"]),
    field("node_displacement", { A: [0, 0], B: [0, 1], C: [0, 0] }),
    field("body_motion", [{ id: 1, u: 0, v: 0, theta: 0 }, { id: 2, u: 0, v: 0.5, theta: -0.125 }]),
  ]);

  it("reads the fields and describes the poles", () => {
    expect(result.movable).toBe(true);
    expect(result.bodies).toHaveLength(2);
    expect(poleText(result.poles[0])).toBe("(7, 0)");
    expect(poleText(result.poles[1])).toBe("∞ ↕ (0, 1)");
    expect(poleText(result.poles[2])).toBe("on a line");
    expect(parsePoleResult([]).rules_agree).toBe(true);
  });

  it("places contradictions at their point, their pole or their body", () => {
    const c = result.contradictions[0];
    expect(contradictionPoint(c, result)).toEqual([2, 0]);
    expect(contradictionPoint({ ...c, at: [1, 1] }, result)).toEqual([1, 1]);
    expect(contradictionPoint({ ...c, pole: "(2)" }, result)).toEqual([7, 0]);
  });

  it("scales the displacement figure to a fraction of the model size and moves bars with their bodies", () => {
    const f = displacementFactor(beam, result, 0.08);
    expect(f).toBeCloseTo((0.08 * 8) / 1); // model size 8 m, max shift 1
    const segs = displacedSegments(beam, result, f);
    expect(segs.map((s) => s.id)).toEqual(["m1", "m2"]);
    expect(segs[0].a).toEqual([0, 0]); // body 1 stays at rest
    expect(displacedSegments(beam, { ...result, bodies: [] }, 2)[1].a).toEqual([4, 2]); // fall back to node displacements
    expect(displacementFactor(beam, { ...result, node_displacement: {}, body_motion: [] }, 0.08)).toBe(0);
  });

  it("writes a report section", () => {
    const md = poleReportExtra(result);
    expect(md).toContain("U = 0");
    expect(md).toContain("| (1,2) | ∞ ↕ (0, 1) | displacement |");
    expect(md).toContain("1. a");
    expect(md).toContain("- Pole (1): no pole");
  });
});

describe("label placement", () => {
  it("treats placed labels as boxes, not points", () => {
    // a label box 20 wide centred at (50, 50): its edge is 10 from the centre
    expect(labelClearance([80, 50], 10, 5, [[50, 50, 10, 5]])).toBe(10);
    expect(labelClearance([60, 50], 10, 5, [[50, 50, 10, 5]])).toBe(0);
    expect(labelClearance([80, 50], 10, 5, [[50, 50]])).toBe(20);
  });
  it("picks the spot that does not overlap a placed label", () => {
    const at = bestLabelSpot([[50, 50], [50, 90]], 20, 7, [[50, 50, 20, 7]], { w: 200, h: 200 });
    expect(at).toEqual([50, 90]);
  });
});
