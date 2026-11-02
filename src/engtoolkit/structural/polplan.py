"""
Pole plan (Polplan) for planar systems of rigid bodies.

The construction works in homogeneous coordinates: a point is (x, y, w) with w = 0 for a point at infinity,
a line is (a, b, c) with a·x + b·y + c·w = 0. Joining two points and intersecting two lines are both
cross products, so parallel lines meet at infinity without special cases.

Procedure: counting criterion, then the pole rules R1 to R8 until nothing changes. A contradiction in a main
pole (i) means body i cannot move, so it is merged into the ground and the construction restarts; a
contradiction in a relative pole (i,j) means the two bodies cannot move against each other, so they are merged.
The exact small-displacement analysis of :mod:`kinematics` is the ground truth the rule-based verdict is
checked against.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import combinations

import numpy as np

from engtoolkit.core.results import Result, rfield

from .kinematics import Displacements, PolePlanInputs, System, build_system

# ---------------- the pole rules ----------------

R1_FIXED = "R1 fixed support"
R2_PIN = "R2 pin support"
R3_ROLLER = "R3 roller (G.O.)"
R4_CLAMP = "R4 sliding clamp"
R5_HINGE = "R5 hinge"
R6_SLIDE = "R6 sleeve/shear"
R7_MAIN = "R7 main-pole theorem"
R8_RELATIVE = "R8 relative-pole theorem"

DIR_TOL = 1e-8     # tolerance on directions (sines of angles)
INF_TOL = 1e-9     # |w| below this (relative to the coordinates) means a point at infinity


# ---------------- homogeneous geometry ----------------

def _canonical_direction(dx: float, dy: float) -> tuple[float, float]:
    n = math.hypot(dx, dy)
    dx, dy = dx / n, dy / n
    if dx < -DIR_TOL or (abs(dx) <= DIR_TOL and dy < 0):
        dx, dy = -dx, -dy
    return dx, dy


def hpoint(x: float, y: float, w: float = 1.0) -> np.ndarray:
    """Normalised homogeneous point: (x, y, 1) if finite, otherwise a unit direction (dx, dy, 0)."""
    if abs(w) > INF_TOL * max(1.0, abs(x), abs(y)):
        return np.array([x / w, y / w, 1.0])
    if math.hypot(x, y) == 0:
        raise ValueError("The zero vector is not a point")
    return np.array([*_canonical_direction(x, y), 0.0])


def point_at_infinity(dx: float, dy: float) -> np.ndarray:
    return hpoint(dx, dy, 0.0)


def hline(a: float, b: float, c: float) -> np.ndarray:
    """Normalised line: unit normal (a, b) with canonical sign; (0, 0, 1) is the line at infinity."""
    n = math.hypot(a, b)
    if n == 0 or n <= INF_TOL * abs(c):
        return np.array([0.0, 0.0, 1.0])
    a, b, c = a / n, b / n, c / n
    if a < -DIR_TOL or (abs(a) <= DIR_TOL and b < 0):
        a, b, c = -a, -b, -c
    return np.array([a, b, c])


def join(p: np.ndarray, q: np.ndarray) -> np.ndarray:
    """Line through two distinct points."""
    v = np.cross(p, q)
    if not np.any(v):
        raise ValueError("Cannot join identical points")
    return hline(*v)


def meet(l1: np.ndarray, l2: np.ndarray) -> np.ndarray:
    """Intersection of two lines; parallel lines meet at infinity."""
    return hpoint(*np.cross(l1, l2))


def is_infinite(p: np.ndarray) -> bool:
    return p[2] == 0.0


def incident(p: np.ndarray, line: np.ndarray, tol: float = 1e-9) -> bool:
    d = abs(float(line @ p))
    return d <= (DIR_TOL if is_infinite(p) else tol)


def same_point(p: np.ndarray, q: np.ndarray, tol: float = 1e-9) -> bool:
    if is_infinite(p) != is_infinite(q):
        return False
    if is_infinite(p):
        return abs(p[0] * q[1] - p[1] * q[0]) <= DIR_TOL
    return math.hypot(p[0] - q[0], p[1] - q[1]) <= tol


def same_line(l1: np.ndarray, l2: np.ndarray, tol: float = 1e-9) -> bool:
    return abs(l1[0] - l2[0]) <= DIR_TOL and abs(l1[1] - l2[1]) <= DIR_TOL and abs(l1[2] - l2[2]) <= tol


def _fmt(x: float) -> str:
    s = f"{x:.4g}"
    return "0" if s in ("-0", "0") else s


def describe_point(p: np.ndarray) -> str:
    if is_infinite(p):
        return f"the point at infinity in direction ({_fmt(p[0])}, {_fmt(p[1])})"
    return f"({_fmt(p[0])}, {_fmt(p[1])})"


def describe_line(l: np.ndarray) -> str:
    a, b, c = l
    if abs(a) <= DIR_TOL and abs(b) <= DIR_TOL:
        return "the line at infinity"
    if abs(b) <= DIR_TOL:
        return f"the vertical line x = {_fmt(-c / a)}"
    if abs(a) <= DIR_TOL:
        return f"the horizontal line y = {_fmt(-c / b)}"
    return f"the line through ({_fmt(-a * c)}, {_fmt(-b * c)}) with direction ({_fmt(-b)}, {_fmt(a)})"


def _circled(i: int) -> str:
    return chr(0x2460 + i - 1) if 1 <= i <= 20 else f"({i})"


def pole_name(key: tuple[int, int]) -> str:
    return f"({key[1]})" if key[0] == 0 else f"({key[0]},{key[1]})"


# ---------------- pole construction ----------------

class Contradiction(Exception):
    def __init__(self, key: tuple[int, int], text: str, at: tuple[float, float] | None):
        super().__init__(text)
        self.key, self.text, self.at = key, text, at


@dataclass
class _Pole:
    point: np.ndarray | None = None
    point_rule: str = ""
    lines: list[np.ndarray] = field(default_factory=list)
    line_rules: list[str] = field(default_factory=list)


def _finite_xy(*points: np.ndarray) -> tuple[float, float] | None:
    for p in points:
        if p is not None and not is_infinite(p):
            return float(p[0]), float(p[1])
    return None


class _Construction:
    """One pass of the rule-based construction for the current set of (merged) bodies."""

    def __init__(self, system: System, find, tol: float, log: list[str]):
        self.system, self.find, self.tol, self.log = system, find, tol, log
        self.poles: dict[tuple[int, int], _Pole] = {}

    def add_point(self, key, pt: np.ndarray, rule: str) -> bool:
        p = self.poles.setdefault(key, _Pole())
        nm = pole_name(key)
        if p.point is not None:
            if same_point(p.point, pt, self.tol):
                return False
            raise Contradiction(key, f"{rule} puts pole {nm} at {describe_point(pt)}, but it is already at "
                                     f"{describe_point(p.point)} ({p.point_rule})", _finite_xy(p.point, pt))
        for line, why in zip(p.lines, p.line_rules):
            if not incident(pt, line, self.tol):
                raise Contradiction(key, f"{rule} puts pole {nm} at {describe_point(pt)}, which is not on "
                                         f"{describe_line(line)} ({why})", _finite_xy(pt))
        p.point, p.point_rule = pt, rule
        self.log.append(f"{rule}: pole {nm} at {describe_point(pt)}")
        return True

    def add_line(self, key, line: np.ndarray, rule: str) -> bool:
        p = self.poles.setdefault(key, _Pole())
        nm = pole_name(key)
        if any(same_line(line, l, self.tol) for l in p.lines):
            return False
        if p.point is not None:
            if not incident(p.point, line, self.tol):
                raise Contradiction(key, f"{rule} requires pole {nm} on {describe_line(line)}, but it is at "
                                         f"{describe_point(p.point)} ({p.point_rule})", _finite_xy(p.point))
            p.lines.append(line)
            p.line_rules.append(rule)
            return False   # bookkeeping only: the point is already known
        if not p.lines:
            p.lines.append(line)
            p.line_rules.append(rule)
            self.log.append(f"{rule}: pole {nm} lies on {describe_line(line)}")
            return True
        pt = meet(p.lines[0], line)
        p.lines.append(line)
        p.line_rules.append(rule)
        p.point, p.point_rule = pt, f"intersection of {describe_line(p.lines[0])} and {describe_line(line)}"
        self.log.append(f"{rule}: pole {nm} lies on {describe_line(line)}; together with "
                        f"{describe_line(p.lines[0])} it is {describe_point(pt)}")
        return True

    def run(self) -> dict[tuple[int, int], _Pole]:
        system, find = self.system, self.find
        for s in system.supports:
            for b in s.bodies:
                r = find(b)
                if r == 0 or s.kind == "fixed":   # fixed supports are handled by R1 before the construction
                    continue
                where = f"at node {s.node}"
                if s.kind == "pin":
                    self.add_point((0, r), hpoint(s.x, s.y), f"{R2_PIN} {where}")
                elif s.kind == "roller":
                    a = math.radians(s.angle)
                    dx, dy = math.cos(a), math.sin(a)
                    self.add_line((0, r), hline(dx, dy, -(dx * s.x + dy * s.y)), f"{R3_ROLLER} {where}")
                else:
                    a = math.radians(s.angle)
                    self.add_point((0, r), point_at_infinity(-math.sin(a), math.cos(a)), f"{R4_CLAMP} {where}")
        for j in system.joints:
            for r1, r2 in combinations(sorted({find(b) for b in j.bodies}), 2):
                if j.kind == "hinge":
                    self.add_point((r1, r2), hpoint(j.x, j.y), f"{R5_HINGE} at node {j.node}")
                else:
                    tx, ty = j.axis
                    dx, dy = (-ty, tx) if j.kind == "sleeve" else (tx, ty)   # direction normal to the allowed slide
                    self.add_point((r1, r2), point_at_infinity(dx, dy), f"{R6_SLIDE} at node {j.node}")
        roots = sorted({find(b.id) for b in system.bodies} - {0})
        ids = [0, *roots]
        for _ in range(10 * len(ids) ** 2 + 10):
            changed = False
            for a, b, c in combinations(ids, 3):
                rule = R7_MAIN if a == 0 else R8_RELATIVE
                keys = [(a, b), (b, c), (a, c)]
                label = f"{rule} for {', '.join(pole_name(k) for k in keys)}"
                for t in (2, 0, 1):   # the pole that receives the line is the one blamed on a contradiction
                    o1, o2 = (self.poles.get(keys[i]) for i in range(3) if i != t)
                    if o1 is None or o2 is None or o1.point is None or o2.point is None:
                        continue
                    if same_point(o1.point, o2.point, self.tol):
                        continue
                    changed |= self.add_line(keys[t], join(o1.point, o2.point), label)
            if not changed:
                return self.poles
        raise RuntimeError("Pole construction did not settle")   # pragma: no cover


# ---------------- exact poles from the displacement mode ----------------

def _exact_pole(motion: tuple[float, float, float], pts: list[tuple[float, float]]) -> np.ndarray | None:
    """Pole of a rigid-body motion over the given points, or None if the points do not move."""
    u, v, th = motion
    wmax = max(math.hypot(u - th * y, v + th * x) for x, y in pts)
    if wmax < 1e-8:
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    diam = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
    if abs(th) * diam <= 1e-8 * wmax:
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        return point_at_infinity(-(v + th * cx), u - th * cy)
    return hpoint(-v / th, u / th)


def _poles_agree(p: np.ndarray, q: np.ndarray, tol: float) -> bool:
    return same_point(p, q, tol)


# ---------------- result ----------------

@dataclass
class PolePlanResult(Result):
    verdict: str = rfield("", "Verdict")
    movable: bool = rfield("", "Kinematically movable")
    dof: int = rfield("", "Degrees of freedom (exact analysis)")
    U: int = rfield("", "Counting number U = (A + z) − 3k")
    A: int = rfield("", "Support reactions A")
    z: int = rfield("", "Joint constraints z")
    k: int = rfield("", "Number of bodies k")
    counting: str = rfield("", "Counting criterion")
    rules_agree: bool = rfield("", "Pole rules agree with the exact analysis")
    bodies: list = rfield("", "Bodies", default_factory=list, summary=False)
    poles: list = rfield("", "Poles", default_factory=list, summary=False)
    loci: list = rfield("", "Geometric loci (lines through poles)", default_factory=list, summary=False)
    contradictions: list = rfield("", "Contradictions", default_factory=list, summary=False)
    steps: list = rfield("", "Steps", default_factory=list, summary=False)
    node_displacement: dict = rfield("m", "Mode shape: node displacement (max = 1)", default_factory=dict, summary=False)
    body_motion: list = rfield("", "Mode shape: body motion (u, v in m, theta in rad)", default_factory=list,
                               summary=False)


def _pole_record(key: tuple[int, int], vec: np.ndarray | None, source: str, status: str) -> dict:
    i, j = (key[1], 0) if key[0] == 0 else key
    rec = {"name": pole_name(key), "i": i, "j": j, "x": None, "y": None, "at_infinity": False,
           "direction": None, "source": source, "status": status}
    if vec is not None:
        if is_infinite(vec):
            rec["at_infinity"] = True
            rec["direction"] = [float(vec[0]), float(vec[1])]
        else:
            rec["x"], rec["y"] = float(vec[0]), float(vec[1])
    return rec


def _line_record(l: np.ndarray) -> tuple[list[float], list[float]]:
    a, b, c = l
    dx, dy = _canonical_direction(-b, a)
    return [float(-a * c) + 0.0, float(-b * c) + 0.0], [dx + 0.0, dy + 0.0]


def analyze_pole_plan(inp: PolePlanInputs) -> PolePlanResult:
    system = build_system(inp)
    exact: Displacements = system.displacements
    tol = 1e-8 * max(1.0, system.size)
    bodies = system.bodies
    steps: list[str] = [f"Counting criterion: {system.counting}"]
    if system.U < 0:
        steps.append(f"U < 0: there are {-system.U} more possible motions than constraints, so the system is "
                     "necessarily movable.")
    elif system.U == 0:
        steps.append("U = 0: just enough constraints. Movable only if they are arranged badly: the pole plan decides.")
    else:
        steps.append(f"U = {system.U} > 0: more constraints than needed. Movable only in an exceptional geometry: "
                     "the pole plan decides.")

    parent = {0: 0, **{b.id: b.id for b in bodies}}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    reason: dict[int, str] = {}
    contradictions: list[dict] = []

    def to_ground(root: int, why: str) -> None:
        for b in bodies:
            if find(b.id) == root:
                reason.setdefault(b.id, why)
        union(root, 0)

    for s in system.supports:   # R1
        if s.kind == "fixed":
            for b in s.bodies:
                if find(b) != 0:
                    steps.append(f"{R1_FIXED} at node {s.node}: body {b} cannot move and becomes part of the ground.")
                    to_ground(find(b), f"{R1_FIXED} at node {s.node}")

    poles: dict[tuple[int, int], _Pole] = {}
    for pass_no in range(1, 2 * len(bodies) + 3):
        roots = sorted({find(b.id) for b in bodies} - {0})
        if not roots:
            steps.append("Every body is part of the ground: nothing can move.")
            poles = {}
            break
        steps.append(f"Pole plan, pass {pass_no}: bodies {', '.join(map(str, roots))} are free, ground = 0.")
        log: list[str] = []
        try:
            poles = _Construction(system, find, tol, log).run()
        except Contradiction as c:
            steps.extend(log)
            key = c.key
            if key[0] == 0:
                contradictions.append({"pole": pole_name(key), "body": key[1], "bodies": [key[1]],
                                       "text": c.text, "at": list(c.at) if c.at else None})
                steps.append(f"Contradiction at {pole_name(key)}: {c.text}. Body {key[1]} cannot move: reduce it into "
                             "the ground (every pole (i,j) with this body becomes (j)) and start again.")
                to_ground(key[1], f"Contradiction at pole {pole_name(key)}")
            else:
                contradictions.append({"pole": pole_name(key), "body": None, "bodies": list(key),
                                       "text": c.text, "at": list(c.at) if c.at else None})
                steps.append(f"Contradiction at {pole_name(key)}: {c.text}. Bodies {key[0]} and {key[1]} cannot move "
                             "against each other: treat them as one body and start again.")
                union(*key)
            continue
        steps.extend(log)
        steps.append("No contradiction and no further change: the construction is finished.")
        break

    rules_movable = any(find(b.id) != 0 for b in bodies)
    rules_agree = rules_movable == exact.movable

    # ----- reconcile with the exact analysis -----
    if not rules_agree:
        if exact.movable:
            steps.append("The pole rules found no way for the system to move, but the exact displacement analysis "
                         f"finds {exact.dof} degree(s) of freedom. The exact result is used.")
            parent = {0: 0, **{b.id: b.id for b in bodies}}
            reason = {}
            if exact.dof == 1:
                for b in bodies:
                    if _exact_pole(exact.body_motion[b.id - 1], _body_points(system, b.id)) is None:
                        reason[b.id] = "no displacement in the exact mode"
                        parent[b.id] = 0
            poles = {}
        else:
            steps.append("The pole rules found no contradiction, but the exact displacement analysis finds no "
                         "possible motion. The exact result is used: the system is immovable.")
            for b in bodies:
                reason.setdefault(b.id, "no displacement in the exact analysis")
                parent[b.id] = 0
            poles = {}

    # ----- poles -----
    roots = sorted({find(b.id) for b in bodies} - {0})
    keys: set[tuple[int, int]] = {(0, r) for r in roots}
    keys |= {k for k, p in poles.items() if p.point is not None or p.lines}
    if not poles and exact.movable:
        for j in system.joints:
            keys |= set(combinations(sorted({find(b) for b in j.bodies}), 2))
    keys = {k for k in keys if k[0] != k[1]}

    def exact_key_pole(key: tuple[int, int]) -> np.ndarray | None:
        if exact.dof != 1:
            return None
        mi = exact.body_motion[key[1] - 1]
        if key[0] == 0:
            return _exact_pole(mi, _body_points(system, key[1]))
        mj = exact.body_motion[key[0] - 1]
        rel = (mi[0] - mj[0], mi[1] - mj[1], mi[2] - mj[2])
        return _exact_pole(rel, _body_points(system, key[0]) + _body_points(system, key[1]))

    vectors: dict[tuple[int, int], np.ndarray | None] = {}
    pole_list: list[dict] = []
    for key in sorted(keys, key=lambda k: (k[0] != 0, k)):
        p = poles.get(key)
        ex = exact_key_pole(key)
        if p is not None and p.point is not None:
            vec, source = p.point, "rule"
            if ex is not None and not _poles_agree(vec, ex, 1e-6 * max(1.0, system.size)):
                rules_agree = False
                steps.append(f"Pole {pole_name(key)} from the rules ({describe_point(vec)}) differs from the exact "
                             f"mode ({describe_point(ex)}); the exact pole is used.")
                vec, source = ex, "displacement"
            pole_list.append(_pole_record(key, vec, source, "determined"))
        elif ex is not None:
            vec = ex
            pole_list.append(_pole_record(key, vec, "displacement", "determined"))
        else:
            vec = None
            status = "line" if p is not None and p.lines else "unknown"
            pole_list.append(_pole_record(key, None, "rule", status))
        vectors[key] = vec

    # ----- loci: lines through poles, identical lines grouped -----
    groups: list[np.ndarray] = []
    for key in sorted(poles, key=lambda k: (k[0] != 0, k)):
        for line in poles[key].lines:
            if not any(same_line(line, g, tol) for g in groups):
                groups.append(line)
    loci = []
    for line in groups:
        if abs(line[0]) <= DIR_TOL and abs(line[1]) <= DIR_TOL:
            continue   # line at infinity: nothing to draw
        on: list[tuple[int, int]] = []
        for key in sorted(vectors, key=lambda k: (k[0] != 0, k)):
            v = vectors[key]
            p = poles.get(key)
            if (v is not None and incident(v, line, tol)) or (p is not None and any(same_line(line, l, tol) for l in p.lines)):
                on.append(key)
        mains = "".join(_circled(k[1]) for k in on if k[0] == 0)
        rels = "".join(pole_name(k) for k in on if k[0] != 0)
        point, direction = _line_record(line)
        loci.append({"label": f"G.O. {mains}{rels}", "poles": [pole_name(k) for k in on],
                     "point": point, "direction": direction})

    # ----- bodies -----
    body_list = []
    for b in bodies:
        root = find(b.id)
        why = reason.get(b.id, "")
        if root not in (0, b.id):
            why = f"cannot move relative to body {root}"
        body_list.append({"id": b.id, "members": b.member_ids, "immovable": root == 0, "reason": why,
                          "label": [b.label[0], b.label[1]], "merged_into": root if root not in (0, b.id) else None})

    # ----- verdict -----
    immovable = [b.id for b in bodies if find(b.id) == 0]
    movable = exact.movable
    if movable:
        verdict = "Movable → statically unusable"
        if immovable:
            verdict += f" (body {immovable[0]} immovable)" if len(immovable) == 1 else \
                f" (bodies {', '.join(map(str, immovable))} immovable)"
    else:
        verdict = "Immovable → statically usable"
    steps.append(f"Exact check (small displacements): {exact.dof} degree(s) of freedom; the pole rules "
                 f"{'agree' if rules_agree else 'DISAGREE'}.")
    steps.append(f"Verdict: {verdict}")

    node_disp = {k: [v[0], v[1]] for k, v in exact.node_disp.items()} if movable else {}
    motion = [{"id": b.id, "u": exact.body_motion[b.id - 1][0], "v": exact.body_motion[b.id - 1][1],
               "theta": exact.body_motion[b.id - 1][2]} for b in bodies] if movable else []
    return PolePlanResult(verdict=verdict, movable=movable, dof=exact.dof, U=system.U, A=system.A, z=system.z,
                          k=system.k, counting=system.counting, rules_agree=rules_agree, bodies=body_list,
                          poles=pole_list, loci=loci, contradictions=contradictions, steps=steps,
                          node_displacement=node_disp, body_motion=motion)


def _body_points(system: System, body_id: int) -> list[tuple[float, float]]:
    return [(system.nodes[n].x, system.nodes[n].y) for n in system.bodies[body_id - 1].nodes]
