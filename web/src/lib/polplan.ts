// Pure logic for the pole-plan editor: model, snapping, hit-testing, edits with undo/redo, view transforms and the
// geometry of the overlays. The kinematics itself stays in Python (structural.pole_plan).
import type { ResultField } from "./types";

export const POLE_TOOL = "structural.pole_plan";

export type JointKind = "rigid" | "hinge" | "sleeve" | "shear";
export type PoleSupportKind = "fixed" | "pin" | "roller" | "clamp";
export type Pt = [number, number];

export type PoleNode = { id: string; x: number; y: number; joint: JointKind };
export type PoleMember = { id: string; a: string; b: string };
export type PoleSupport = { node: string; kind: PoleSupportKind; angle: number };
export type PoleModel = { nodes: PoleNode[]; members: PoleMember[]; supports: PoleSupport[] };

export const JOINTS: JointKind[] = ["rigid", "hinge", "sleeve", "shear"];
export const POLE_SUPPORTS: PoleSupportKind[] = ["fixed", "pin", "roller", "clamp"];
export const EMPTY_MODEL: PoleModel = { nodes: [], members: [], supports: [] };

/** Round away float noise (1e-6 m) and turn -0 into 0. */
export const round6 = (v: number): number => Math.round(v * 1e6) / 1e6 + 0;

export function snap(v: number, step: number): number {
  return round6(Math.round(v / step) * step);
}

export const snapPoint = (p: Pt, step: number): Pt => [snap(p[0], step), snap(p[1], step)];

// ---------------- hit testing ----------------

const dist = (a: Pt, b: Pt) => Math.hypot(a[0] - b[0], a[1] - b[1]);
const pos = (n: PoleNode): Pt => [n.x, n.y];
export const nodeById = (m: PoleModel, id: string): PoleNode | undefined => m.nodes.find((n) => n.id === id);

/** Distance from p to segment ab and the parameter t of the closest point (0 at a, 1 at b). */
export function distToSegment(p: Pt, a: Pt, b: Pt): { d: number; t: number } {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const len2 = dx * dx + dy * dy;
  const t = len2 === 0 ? 0 : Math.min(1, Math.max(0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2));
  return { d: dist(p, [a[0] + t * dx, a[1] + t * dy]), t };
}

/** Nearest node within `tol` metres of p. */
export function nodeAt(m: PoleModel, p: Pt, tol: number): PoleNode | null {
  let best: PoleNode | null = null;
  let bd = tol;
  for (const n of m.nodes) {
    const d = dist(p, pos(n));
    if (d <= bd) { best = n; bd = d; }
  }
  return best;
}

/** Nearest member within `tol` metres of p, with the closest point on it. */
export function memberAt(m: PoleModel, p: Pt, tol: number): { member: PoleMember; t: number; point: Pt } | null {
  let best: { member: PoleMember; t: number; point: Pt } | null = null;
  let bd = tol;
  for (const mem of m.members) {
    const a = nodeById(m, mem.a);
    const b = nodeById(m, mem.b);
    if (!a || !b) continue;
    const { d, t } = distToSegment(p, pos(a), pos(b));
    if (d <= bd) { best = { member: mem, t, point: [a.x + t * (b.x - a.x), a.y + t * (b.y - a.y)] }; bd = d; }
  }
  return best;
}

/** Unit vectors from a node to the other ends of its members. */
function neighbours(m: PoleModel, id: string): Pt[] {
  const n = nodeById(m, id);
  if (!n) return [];
  const out: Pt[] = [];
  for (const mem of m.members) {
    const other = mem.a === id ? nodeById(m, mem.b) : mem.b === id ? nodeById(m, mem.a) : undefined;
    if (!other) continue;
    const d = Math.hypot(other.x - n.x, other.y - n.y);
    if (d > 0) out.push([(other.x - n.x) / d, (other.y - n.y) / d]);
  }
  return out;
}

/** Direction of the members at a node (first member's direction, used to orient sleeve / shear symbols). */
export function memberAxis(m: PoleModel, id: string): Pt {
  return neighbours(m, id)[0] ?? [1, 0];
}

/**
 * Unit vector from the node towards the body of its support symbol (model coordinates, y up). Pins stand below the
 * node, rollers on the side of their ground, walls behind the member end; the symbol avoids the members.
 */
export function supportSide(m: PoleModel, s: PoleSupport): Pt {
  const nb = neighbours(m, s.node);
  const mean: Pt = nb.length ? [nb.reduce((a, v) => a + v[0], 0) / nb.length, nb.reduce((a, v) => a + v[1], 0) / nb.length] : [0, 0];
  const mlen = Math.hypot(mean[0], mean[1]);
  if (s.kind === "pin") return mean[1] < -0.5 ? [0, 1] : [0, -1];
  if (s.kind === "fixed") return mlen > 0.3 ? [round6(-mean[0] / mlen), round6(-mean[1] / mlen)] : [-1, 0];
  const a = (s.angle * Math.PI) / 180;
  let side: Pt = [Math.sin(a), -Math.cos(a)]; // -normal of the free direction: ground below a horizontal roller
  if (mean[0] * side[0] + mean[1] * side[1] > 0.3) side = [-side[0], -side[1]];
  return [round6(side[0]), round6(side[1])];
}

export type Hit = { kind: "node"; id: string } | { kind: "support"; node: string } | { kind: "member"; id: string } | null;

/** What lies under p: nodes first, then support symbols (a segment of `symbolLen` metres from the node), then members. */
export function hitTest(m: PoleModel, p: Pt, tol: number, symbolLen: number): Hit {
  const n = nodeAt(m, p, tol);
  if (n) return { kind: "node", id: n.id };
  for (const s of m.supports) {
    const node = nodeById(m, s.node);
    if (!node) continue;
    const side = supportSide(m, s);
    const end: Pt = [node.x + side[0] * symbolLen, node.y + side[1] * symbolLen];
    if (distToSegment(p, pos(node), end).d <= tol) return { kind: "support", node: s.node };
  }
  const mem = memberAt(m, p, tol);
  return mem ? { kind: "member", id: mem.member.id } : null;
}

// ---------------- model edits (all pure; a no-op returns the same object) ----------------

function nextId(prefix: string, ids: string[]): string {
  const used = new Set(ids);
  let k = 1;
  for (const id of ids) {
    const mt = new RegExp(`^${prefix}(\\d+)$`).exec(id);
    if (mt) k = Math.max(k, Number(mt[1]) + 1);
  }
  while (used.has(`${prefix}${k}`)) k++;
  return `${prefix}${k}`;
}

export function addNode(m: PoleModel, x: number, y: number, joint: JointKind = "rigid"): { model: PoleModel; id: string } {
  const id = nextId("n", m.nodes.map((n) => n.id));
  return { model: { ...m, nodes: [...m.nodes, { id, x: round6(x), y: round6(y), joint }] }, id };
}

/** Insert a node on a member, splitting it in two (the first part keeps the member id). */
export function splitMember(m: PoleModel, memberId: string, p: Pt): { model: PoleModel; id: string } {
  const mem = m.members.find((x) => x.id === memberId);
  if (!mem) return addNode(m, p[0], p[1]);
  const { model, id } = addNode(m, p[0], p[1]);
  const mid = nextId("m", m.members.map((x) => x.id));
  const members = model.members.flatMap((x) => (x.id === memberId ? [{ ...x, b: id }, { id: mid, a: id, b: mem.b }] : [x]));
  return { model: { ...model, members }, id };
}

export type PickOpts = { tol: number; step: number };

/**
 * Node for a click at raw point p: an existing node within tol, the point on a member (splitting it) or a new node on
 * the grid. A member click lands on the snapped point when that lies on the member, else on the projection.
 */
export function pickNode(m: PoleModel, raw: Pt, { tol, step }: PickOpts): { model: PoleModel; id: string } {
  const near = nodeAt(m, raw, tol);
  if (near) return { model: m, id: near.id };
  const snapped = snapPoint(raw, step);
  const onSnapped = nodeAt(m, snapped, 1e-6);
  if (onSnapped) return { model: m, id: onSnapped.id };
  const hit = memberAt(m, raw, tol);
  if (hit) {
    const a = nodeById(m, hit.member.a)!;
    const b = nodeById(m, hit.member.b)!;
    const onMember = distToSegment(snapped, pos(a), pos(b));
    const strictlyInside = onMember.t > 1e-9 && onMember.t < 1 - 1e-9;
    const p: Pt = onMember.d < 1e-6 && strictlyInside ? snapped : [round6(hit.point[0]), round6(hit.point[1])];
    return splitMember(m, hit.member.id, p);
  }
  const grid = memberAt(m, snapped, 1e-6);
  if (grid) return splitMember(m, grid.member.id, snapped);
  return addNode(m, snapped[0], snapped[1]);
}

export function addMember(m: PoleModel, a: string, b: string): PoleModel {
  if (a === b) return m;
  if (m.members.some((x) => (x.a === a && x.b === b) || (x.a === b && x.b === a))) return m;
  if (!nodeById(m, a) || !nodeById(m, b)) return m;
  return { ...m, members: [...m.members, { id: nextId("m", m.members.map((x) => x.id)), a, b }] };
}

/** Remove nodes (and their supports) that no member touches any more, limited to the candidate ids. */
function dropOrphans(m: PoleModel, candidates: string[]): PoleModel {
  const used = new Set(m.members.flatMap((x) => [x.a, x.b]));
  const gone = new Set(candidates.filter((id) => !used.has(id)));
  if (!gone.size) return m;
  return { nodes: m.nodes.filter((n) => !gone.has(n.id)), members: m.members, supports: m.supports.filter((s) => !gone.has(s.node)) };
}

export function removeMember(m: PoleModel, id: string): PoleModel {
  const mem = m.members.find((x) => x.id === id);
  if (!mem) return m;
  return dropOrphans({ ...m, members: m.members.filter((x) => x.id !== id) }, [mem.a, mem.b]);
}

/** Deleting a node removes its members and supports; neighbours left without a member go too. */
export function removeNode(m: PoleModel, id: string): PoleModel {
  if (!nodeById(m, id)) return m;
  const touching = m.members.filter((x) => x.a === id || x.b === id);
  const others = touching.map((x) => (x.a === id ? x.b : x.a));
  const next: PoleModel = {
    nodes: m.nodes.filter((n) => n.id !== id),
    members: m.members.filter((x) => x.a !== id && x.b !== id),
    supports: m.supports.filter((s) => s.node !== id),
  };
  return dropOrphans(next, others);
}

export function removeSupport(m: PoleModel, node: string): PoleModel {
  return m.supports.some((s) => s.node === node) ? { ...m, supports: m.supports.filter((s) => s.node !== node) } : m;
}

export function moveNode(m: PoleModel, id: string, x: number, y: number): PoleModel {
  const n = nodeById(m, id);
  if (!n || (n.x === x && n.y === y)) return m;
  return { ...m, nodes: m.nodes.map((v) => (v.id === id ? { ...v, x, y } : v)) };
}

/** Set the joint type of a node; choosing the type a node already has turns it back into a rigid node. */
export function toggleJoint(m: PoleModel, id: string, joint: JointKind): PoleModel {
  const n = nodeById(m, id);
  if (!n) return m;
  const next: JointKind = n.joint === joint ? "rigid" : joint;
  return { ...m, nodes: m.nodes.map((v) => (v.id === id ? { ...v, joint: next } : v)) };
}

/** Place (or replace) the support of a node; placing the same kind again keeps it (and its angle). */
export function setSupport(m: PoleModel, node: string, kind: PoleSupportKind, angle = 0): PoleModel {
  if (!nodeById(m, node)) return m;
  const cur = m.supports.find((s) => s.node === node);
  if (cur?.kind === kind) return m;
  const next: PoleSupport = { node, kind, angle: kind === "roller" || kind === "clamp" ? angle : 0 };
  return { ...m, supports: cur ? m.supports.map((s) => (s.node === node ? next : s)) : [...m.supports, next] };
}

export const hasAngle = (kind: PoleSupportKind): boolean => kind === "roller" || kind === "clamp";

/** Free direction of a roller / sliding clamp, in degrees (0 = horizontal) folded into [0, 180). */
export function setSupportAngle(m: PoleModel, node: string, angle: number): PoleModel {
  const s = m.supports.find((x) => x.node === node);
  if (!s || !hasAngle(s.kind) || !Number.isFinite(angle)) return m;
  const a = round6(((angle % 180) + 180) % 180);
  return a === s.angle ? m : { ...m, supports: m.supports.map((x) => (x.node === node ? { ...x, angle: a } : x)) };
}

export const rotateSupport = (m: PoleModel, node: string, delta = 90): PoleModel => {
  const s = m.supports.find((x) => x.node === node);
  return s ? setSupportAngle(m, node, s.angle + delta) : m;
};

/** What the Python tool gets: nodes no member touches (and their supports) are left out. */
export function toolInputs(m: PoleModel): PoleModel {
  const used = new Set(m.members.flatMap((x) => [x.a, x.b]));
  return {
    nodes: m.nodes.filter((n) => used.has(n.id)).map((n) => ({ id: n.id, x: round6(n.x), y: round6(n.y), joint: n.joint })),
    members: m.members.map((x) => ({ id: x.id, a: x.a, b: x.b })),
    supports: m.supports.filter((s) => used.has(s.node)).map((s) => ({ node: s.node, kind: s.kind, angle: s.angle })),
  };
}

export const hasMembers = (m: PoleModel): boolean => m.members.length > 0;

const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);

/** Sanitise a model decoded from a URL or the tool schema: unknown shapes give null, bad entries are dropped. */
export function normalizeModel(raw: unknown): PoleModel | null {
  if (!isRecord(raw) || !Array.isArray(raw.nodes) || !Array.isArray(raw.members)) return null;
  const nodes: PoleNode[] = [];
  for (const n of raw.nodes) {
    if (!isRecord(n) || typeof n.id !== "string" || typeof n.x !== "number" || typeof n.y !== "number" || !Number.isFinite(n.x) || !Number.isFinite(n.y)) continue;
    if (nodes.some((v) => v.id === n.id)) continue;
    nodes.push({ id: n.id, x: n.x, y: n.y, joint: JOINTS.includes(n.joint as JointKind) ? (n.joint as JointKind) : "rigid" });
  }
  const ids = new Set(nodes.map((n) => n.id));
  const members: PoleMember[] = [];
  for (const x of raw.members) {
    if (!isRecord(x) || typeof x.id !== "string" || typeof x.a !== "string" || typeof x.b !== "string") continue;
    if (!ids.has(x.a) || !ids.has(x.b) || members.some((v) => v.id === x.id)) continue;
    members.push({ id: x.id, a: x.a, b: x.b });
  }
  const supports: PoleSupport[] = [];
  for (const s of Array.isArray(raw.supports) ? raw.supports : []) {
    if (!isRecord(s) || typeof s.node !== "string" || !ids.has(s.node) || !POLE_SUPPORTS.includes(s.kind as PoleSupportKind)) continue;
    if (supports.some((v) => v.node === s.node)) continue;
    supports.push({ node: s.node, kind: s.kind as PoleSupportKind, angle: typeof s.angle === "number" && Number.isFinite(s.angle) ? s.angle : 0 });
  }
  return { nodes, members, supports };
}

// ---------------- undo / redo ----------------

export type History<T> = { past: T[]; future: T[] };
export const emptyHistory = <T,>(): History<T> => ({ past: [], future: [] });

/** Remember `current` before it is replaced by a new state. */
export function record<T>(h: History<T>, current: T, limit = 200): History<T> {
  return { past: [...h.past, current].slice(-limit), future: [] };
}

export function undo<T>(h: History<T>, current: T): { history: History<T>; value: T } | null {
  if (!h.past.length) return null;
  return { value: h.past[h.past.length - 1], history: { past: h.past.slice(0, -1), future: [current, ...h.future] } };
}

export function redo<T>(h: History<T>, current: T): { history: History<T>; value: T } | null {
  if (!h.future.length) return null;
  return { value: h.future[0], history: { past: [...h.past, current], future: h.future.slice(1) } };
}

// ---------------- view ----------------

/** The model point at the centre of the canvas and the scale in pixels per metre. */
export type View = { cx: number; cy: number; scale: number };
export const MIN_SCALE = 3;
export const MAX_SCALE = 600;

export const toScreen = (v: View, w: number, h: number, p: Pt): Pt => [w / 2 + (p[0] - v.cx) * v.scale, h / 2 - (p[1] - v.cy) * v.scale];
export const toModel = (v: View, w: number, h: number, s: Pt): Pt => [v.cx + (s[0] - w / 2) / v.scale, v.cy - (s[1] - h / 2) / v.scale];

/** Zoom by `factor` keeping the model point under the screen position `s` fixed. */
export function zoomAt(v: View, w: number, h: number, s: Pt, factor: number): View {
  const scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, v.scale * factor));
  const p = toModel(v, w, h, s);
  return { scale, cx: p[0] - (s[0] - w / 2) / scale, cy: p[1] + (s[1] - h / 2) / scale };
}

export const panBy = (v: View, dx: number, dy: number): View => ({ ...v, cx: v.cx - dx / v.scale, cy: v.cy + dy / v.scale });

export function modelBounds(m: PoleModel): { minX: number; minY: number; maxX: number; maxY: number } | null {
  if (!m.nodes.length) return null;
  const xs = m.nodes.map((n) => n.x);
  const ys = m.nodes.map((n) => n.y);
  return { minX: Math.min(...xs), minY: Math.min(...ys), maxX: Math.max(...xs), maxY: Math.max(...ys) };
}

/** Diagonal of the bounding box (at least 1 m so a lone node still has a size). */
export function modelSize(m: PoleModel): number {
  const b = modelBounds(m);
  return b ? Math.max(1, Math.hypot(b.maxX - b.minX, b.maxY - b.minY)) : 1;
}

export function fitView(m: PoleModel, w: number, h: number, margin = 64): View {
  const b = modelBounds(m);
  if (!b || w <= 0 || h <= 0) return { cx: 5, cy: 1, scale: 40 };
  const bw = Math.max(b.maxX - b.minX, 1);
  const bh = Math.max(b.maxY - b.minY, 1);
  const scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, Math.min((w - 2 * margin) / bw, (h - 2 * margin) / bh)));
  return { cx: (b.minX + b.maxX) / 2, cy: (b.minY + b.maxY) / 2, scale };
}

export const GRID_STEPS = [0.5, 1, 2] as const;

// ---------------- overlay geometry ----------------

export type Rect = { minX: number; minY: number; maxX: number; maxY: number };

/** The part of the infinite line (point + t·dir) inside the rectangle, or null. */
export function clipLine(point: Pt, dir: Pt, r: Rect): [Pt, Pt] | null {
  let t0 = -Infinity;
  let t1 = Infinity;
  const axes: [number, number, number, number][] = [[point[0], dir[0], r.minX, r.maxX], [point[1], dir[1], r.minY, r.maxY]];
  for (const [p, d, lo, hi] of axes) {
    if (Math.abs(d) < 1e-12) {
      if (p < lo || p > hi) return null;
    } else {
      const a = (lo - p) / d;
      const b = (hi - p) / d;
      t0 = Math.max(t0, Math.min(a, b));
      t1 = Math.min(t1, Math.max(a, b));
    }
  }
  if (!(t0 < t1)) return null;
  return [[point[0] + t0 * dir[0], point[1] + t0 * dir[1]], [point[0] + t1 * dir[0], point[1] + t1 * dir[1]]];
}

/** Where the ray from `origin` along `dir` (screen space, y down) leaves the canvas shrunk by `inset` px. */
export function rayToEdge(origin: Pt, dir: Pt, w: number, h: number, inset: number): Pt {
  const o: Pt = [Math.min(w - inset, Math.max(inset, origin[0])), Math.min(h - inset, Math.max(inset, origin[1]))];
  const len = Math.hypot(dir[0], dir[1]) || 1;
  const d: Pt = [dir[0] / len, dir[1] / len];
  let t = Infinity;
  if (d[0] > 1e-9) t = Math.min(t, (w - inset - o[0]) / d[0]);
  if (d[0] < -1e-9) t = Math.min(t, (inset - o[0]) / d[0]);
  if (d[1] > 1e-9) t = Math.min(t, (h - inset - o[1]) / d[1]);
  if (d[1] < -1e-9) t = Math.min(t, (inset - o[1]) / d[1]);
  if (!Number.isFinite(t)) t = 0;
  return [o[0] + t * d[0], o[1] + t * d[1]];
}

export type InfinityMark = { name: string; pos: Pt; dir: Pt };

/**
 * Marks for poles at infinity: each sits near the canvas edge along its direction from `origin` (all in screen space).
 * Marks that would sit within `minGap` px of an earlier one go to the legend instead.
 */
export function placeInfinityPoles(
  poles: { name: string; direction: Pt }[], origin: Pt, w: number, h: number, inset = 34, minGap = 44,
): { marks: InfinityMark[]; legend: { name: string; dir: Pt }[] } {
  const marks: InfinityMark[] = [];
  const legend: { name: string; dir: Pt }[] = [];
  for (const p of poles) {
    const dir: Pt = [p.direction[0], -p.direction[1]]; // model y up -> screen y down
    const pos = rayToEdge(origin, dir, w, h, inset);
    if (marks.some((m) => dist(m.pos, pos) < minGap)) legend.push({ name: p.name, dir: p.direction });
    else marks.push({ name: p.name, pos, dir });
  }
  return { marks, legend };
}

/**
 * Offsets (px) for labels at nearly coincident points: the first of a cluster keeps its place, the others sit on a ring
 * around it (the caller draws leader lines when the offset is not zero).
 */
export function clusterOffsets(points: Pt[], radius = 14, ring = 24): Pt[] {
  const out: Pt[] = points.map(() => [0, 0]);
  const cluster: number[] = points.map(() => -1);
  const heads: number[] = [];
  const members: number[][] = [];
  points.forEach((p, i) => {
    const c = heads.findIndex((h) => dist(points[h], p) <= radius);
    if (c < 0) { heads.push(i); members.push([i]); cluster[i] = heads.length - 1; } else { members[c].push(i); cluster[i] = c; }
  });
  for (const group of members) {
    group.slice(1).forEach((i, k) => {
      const ang = (-45 - 80 * k) * (Math.PI / 180);
      out[i] = [Math.cos(ang) * ring, Math.sin(ang) * ring];
    });
  }
  return out;
}

export const directionAngle = (d: Pt): number => {
  const a = (Math.atan2(d[1], d[0]) * 180) / Math.PI;
  return round6(((a % 180) + 180) % 180);
};

/** Arrow glyph for a direction (undirected): ↔ ↕ ⤢ ⤡. */
export function directionArrow(d: Pt): string {
  const a = directionAngle(d);
  if (a < 7 || a > 173) return "↔";
  if (Math.abs(a - 90) < 7) return "↕";
  return a < 90 ? "⤢" : "⤡";
}

// ---------------- tool result ----------------

export type PoleBody = { id: number; members: string[]; immovable: boolean; reason: string; label: Pt; merged_into: number | null };
export type PolePoint = {
  name: string; i: number; j: number; x: number | null; y: number | null; at_infinity: boolean; direction: Pt | null;
  source: "rule" | "displacement"; status: "determined" | "line" | "unknown";
};
export type PoleLocus = { label: string; poles: string[]; point: Pt; direction: Pt };
export type PoleContradiction = { pole: string; body: number; bodies: number[]; text: string; at: Pt | null };
export type PoleBodyMotion = { id: number; u: number; v: number; theta: number };
export type PoleResult = {
  verdict: string; movable: boolean; dof: number; U: number; A: number; z: number; k: number; counting: string; rules_agree: boolean;
  bodies: PoleBody[]; poles: PolePoint[]; loci: PoleLocus[]; contradictions: PoleContradiction[]; steps: string[];
  node_displacement: Record<string, Pt>; body_motion: PoleBodyMotion[];
};

/** The tool's result fields as a typed object (missing fields get neutral values). */
export function parsePoleResult(fields: ResultField[]): PoleResult {
  const v: Record<string, unknown> = Object.fromEntries(fields.map((f) => [f.name, f.value]));
  const arr = <T,>(x: unknown): T[] => (Array.isArray(x) ? (x as T[]) : []);
  return {
    verdict: String(v.verdict ?? ""), movable: Boolean(v.movable), dof: Number(v.dof ?? 0), U: Number(v.U ?? 0), A: Number(v.A ?? 0),
    z: Number(v.z ?? 0), k: Number(v.k ?? 0), counting: String(v.counting ?? ""), rules_agree: v.rules_agree !== false,
    bodies: arr<PoleBody>(v.bodies), poles: arr<PolePoint>(v.poles), loci: arr<PoleLocus>(v.loci),
    contradictions: arr<PoleContradiction>(v.contradictions), steps: arr<string>(v.steps),
    node_displacement: isRecord(v.node_displacement) ? (v.node_displacement as Record<string, Pt>) : {},
    body_motion: arr<PoleBodyMotion>(v.body_motion),
  };
}

/** Pole position text for tables: coordinates, or "∞ ↕ (dx, dy)" for poles at infinity. */
export function poleText(p: PolePoint, fmt: (v: number) => string = (v) => String(round6(v))): string {
  if (p.at_infinity && p.direction) return `∞ ${directionArrow(p.direction)} (${fmt(p.direction[0])}, ${fmt(p.direction[1])})`;
  if (p.x === null || p.y === null) return p.status === "line" ? "on a line" : "undetermined";
  return `(${fmt(p.x)}, ${fmt(p.y)})`;
}

/** Position a contradiction is drawn at: its own point, else the named pole, else the first body's label. */
export function contradictionPoint(c: PoleContradiction, r: PoleResult): Pt | null {
  if (c.at) return c.at;
  const p = r.poles.find((x) => x.name === c.pole);
  if (p && p.x !== null && p.y !== null) return [p.x, p.y];
  const b = r.bodies.find((x) => x.id === c.body);
  return b ? b.label : null;
}

// ---------------- displacement figure ----------------

export type Segment = { id: string; a: Pt; b: Pt };

/** Largest displacement of any node (1 in the tool's normalisation). */
export function maxDisplacement(r: PoleResult): number {
  let mx = 0;
  for (const d of Object.values(r.node_displacement)) mx = Math.max(mx, Math.hypot(d[0], d[1]));
  for (const b of r.body_motion) mx = Math.max(mx, Math.hypot(b.u, b.v));
  return mx;
}

/** Factor for which the largest node shift is `fraction` of the model size. */
export function displacementFactor(m: PoleModel, r: PoleResult, fraction: number): number {
  const mx = maxDisplacement(r);
  return mx > 1e-12 ? (fraction * modelSize(m)) / mx : 0;
}

/**
 * The deformed system: each member moves with its body (u − θy, v + θx) when the body is known, otherwise its end nodes
 * follow the node displacements.
 */
export function displacedSegments(m: PoleModel, r: PoleResult, factor: number): Segment[] {
  const bodyOf = new Map<string, number>();
  for (const b of r.bodies) for (const id of b.members) bodyOf.set(id, b.id);
  const motion = new Map(r.body_motion.map((b) => [b.id, b]));
  const out: Segment[] = [];
  for (const mem of m.members) {
    const na = nodeById(m, mem.a);
    const nb = nodeById(m, mem.b);
    if (!na || !nb) continue;
    const mo = motion.get(bodyOf.get(mem.id) ?? -1);
    const move = (n: PoleNode): Pt => {
      if (mo) return [n.x + factor * (mo.u - mo.theta * n.y), n.y + factor * (mo.v + mo.theta * n.x)];
      const d = r.node_displacement[n.id] ?? [0, 0];
      return [n.x + factor * d[0], n.y + factor * d[1]];
    };
    out.push({ id: mem.id, a: move(na), b: move(nb) });
  }
  return out;
}

// ---------------- example presets ----------------

export type PolePreset = { id: string; label: string; model: PoleModel };

/** Straight beam along y = 0 through the x positions (nodes n1, n2, ...); joints and supports by node index (0-based). */
function beam(xs: number[], joints: Record<number, JointKind>, supports: Record<number, PoleSupport["kind"] | [PoleSupport["kind"], number]>): PoleModel {
  const nodes = xs.map((x, i) => ({ id: `n${i + 1}`, x, y: 0, joint: joints[i] ?? ("rigid" as JointKind) }));
  const members = xs.slice(1).map((_, i) => ({ id: `m${i + 1}`, a: `n${i + 1}`, b: `n${i + 2}` }));
  const sup: PoleSupport[] = Object.entries(supports).map(([i, s]) => {
    const [kind, angle] = Array.isArray(s) ? s : [s, 0];
    return { node: `n${Number(i) + 1}`, kind, angle };
  });
  return { nodes, members, supports: sup };
}

function trussTwoBands(): PoleModel {
  // upper Warren band: 5 panels of 2 m, 1.2 m deep, pinned at its left end;
  // lower band: 3 panels below it, on a roller that slides vertically against a wall
  const pts: Record<string, Pt> = {};
  const pairs: [string, string][] = [];
  const band = (chord: string, apex: string, x0: number, y: number, dy: number, panels: number) => {
    for (let i = 0; i <= panels; i++) pts[`${chord}${i}`] = [x0 + 2 * i, y];
    for (let i = 0; i < panels; i++) {
      pts[`${apex}${i}`] = [x0 + 2 * i + 1, y + dy];
      pairs.push([`${chord}${i}`, `${chord}${i + 1}`], [`${chord}${i}`, `${apex}${i}`], [`${apex}${i}`, `${chord}${i + 1}`]);
      if (i > 0) pairs.push([`${apex}${i - 1}`, `${apex}${i}`]);
    }
  };
  band("S", "T", 0, 0, 1.2, 5);
  band("W", "X", 4, -3, -1.2, 3);
  // the two linking bars: inclined and vertical
  pairs.push(["S2", "W2"], ["S5", "W3"]);
  return {
    nodes: Object.entries(pts).map(([id, [x, y]]) => ({ id, x, y, joint: "hinge" as JointKind })),
    members: pairs.map(([a, b], i) => ({ id: `m${i + 1}`, a, b })),
    supports: [{ node: "S0", kind: "pin", angle: 0 }, { node: "W0", kind: "roller", angle: 90 }],
  };
}

export const POLE_PRESETS: PolePreset[] = [
  {
    id: "two-hinge", label: "Two-hinge continuous beam",
    model: beam([0, 4, 7, 9, 14], { 2: "hinge", 3: "hinge" }, { 0: "pin", 1: "roller", 4: "pin" }),
  },
  {
    id: "two-hinge-four", label: "Two-hinge beam on four supports",
    model: beam([0, 4, 7, 9, 11, 14], { 2: "hinge", 3: "hinge" }, { 0: "pin", 1: "roller", 4: "roller", 5: "roller" }),
  },
  { id: "sleeve", label: "Beam with sliding sleeve", model: beam([0, 5, 10], { 1: "sleeve" }, { 0: "pin", 2: "roller" }) },
  { id: "truss", label: "Truss: two bands linked by two bars", model: trussTwoBands() },
  {
    id: "arch", label: "Three-hinged arch",
    model: {
      nodes: [{ id: "A", x: 0, y: 0, joint: "rigid" }, { id: "C", x: 4, y: 3, joint: "hinge" }, { id: "B", x: 8, y: 0, joint: "rigid" }],
      members: [{ id: "m1", a: "A", b: "C" }, { id: "m2", a: "C", b: "B" }],
      supports: [{ node: "A", kind: "pin", angle: 0 }, { node: "B", kind: "pin", angle: 0 }],
    },
  },
  {
    id: "four-bar", label: "Four-bar linkage",
    model: {
      nodes: [{ id: "A", x: 0, y: 0, joint: "hinge" }, { id: "B", x: 1, y: 3, joint: "hinge" }, { id: "C", x: 5, y: 3, joint: "hinge" }, { id: "D", x: 4, y: 0, joint: "hinge" }],
      members: [{ id: "m1", a: "A", b: "B" }, { id: "m2", a: "B", b: "C" }, { id: "m3", a: "C", b: "D" }],
      supports: [{ node: "A", kind: "pin", angle: 0 }, { node: "D", kind: "pin", angle: 0 }],
    },
  },
];

export const DEFAULT_POLE_MODEL: PoleModel = POLE_PRESETS[0].model;

/** Markdown appended to the generic report: counting criterion, contradictions, poles and steps. */
export function poleReportExtra(r: PoleResult): string {
  const lines = ["", "", "## Counting criterion", "", r.counting, "", `Verdict: **${r.verdict}**${r.rules_agree ? "" : " (the pole rules and the exact analysis disagree)"}`];
  if (r.contradictions.length) lines.push("", "## Contradictions", "", ...r.contradictions.map((c) => `- Pole ${c.pole}: ${c.text}`));
  if (r.poles.length) {
    lines.push("", "## Poles", "", "| Pole | Position (m) | Source |", "|---|---|---|", ...r.poles.map((p) => `| ${p.name} | ${poleText(p)} | ${p.source} |`));
  }
  if (r.steps.length) lines.push("", "## Steps", "", ...r.steps.map((s, i) => `${i + 1}. ${s}`));
  return lines.join("\n") + "\n";
}

// ---------------- label placement ----------------

/** A point [x, y] or a box [cx, cy, halfW, halfH] (an already placed label). */
export type Obstacle = Pt | [number, number, number, number];

/** Distance from the nearest obstacle to the label box (centre c, half sizes); 0 when they overlap. */
export function labelClearance(c: Pt, halfW: number, halfH: number, obstacles: Obstacle[]): number {
  let m = Infinity;
  for (const o of obstacles) {
    const dx = Math.max(Math.abs(o[0] - c[0]) - halfW - (o[2] ?? 0), 0);
    const dy = Math.max(Math.abs(o[1] - c[1]) - halfH - (o[3] ?? 0), 0);
    m = Math.min(m, Math.hypot(dx, dy));
  }
  return m;
}

/**
 * The candidate whose label box keeps the most distance from the obstacles and stays inside the canvas (first on ties).
 * Clearance beyond ``enough`` counts the same, so an early (preferred) candidate with room wins over a later, emptier one.
 */
export function bestLabelSpot(cands: Pt[], halfW: number, halfH: number, obstacles: Obstacle[], bounds: { w: number; h: number },
                              enough = Infinity): Pt {
  let best: Pt | null = null;
  let bc = -Infinity;
  for (const c of cands) {
    if (c[0] - halfW < 2 || c[0] + halfW > bounds.w - 2 || c[1] - halfH < 2 || c[1] + halfH > bounds.h - 2) continue;
    const cl = Math.min(labelClearance(c, halfW, halfH, obstacles), enough);
    if (cl > bc + 1e-9) { bc = cl; best = c; }
  }
  return best ?? cands[0];
}
