"""
Kinematic model of planar systems of rigid bodies: input model, body detection, counting criterion
and an exact small-displacement analysis (the ground truth for the pole plan in ``polplan``).

Conventions (small displacements): body ``b`` moves with (u, v, θ) about the origin, so the displacement
of a point p is (u − θ·p_y, v + θ·p_x). Hinge nodes get their own point unknown (ux, uy) that every body
meeting there must follow.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field, model_validator

from engtoolkit.core.registry import Input

JointType = Literal["rigid", "hinge", "sleeve", "shear"]
SupportKind = Literal["fixed", "pin", "roller", "clamp"]

SUPPORT_REACTIONS: dict[str, int] = {"fixed": 3, "pin": 2, "roller": 1, "clamp": 2}
RANK_RTOL = 1e-9    # singular values below this fraction of the largest count as zero
MERGE_RTOL = 1e-6   # bodies whose free-system motion differs by less than this fraction are one body


# ---------------- input model ----------------

class NodeInput(BaseModel):
    id: str = Field(min_length=1, description="Node id")
    x: float = Input(0.0, "m", "x")
    y: float = Input(0.0, "m", "y")
    joint: JointType = Input("rigid", "", "Joint: rigid (welded), hinge, sleeve (slides along the axis) or shear (slides across the axis)")


class MemberInput(BaseModel):
    id: str = Field(min_length=1, description="Member id")
    a: str = Field(min_length=1, description="Start node id")
    b: str = Field(min_length=1, description="End node id")


class SupportInput(BaseModel):
    node: str = Field(min_length=1, description="Node id")
    kind: SupportKind = Input("pin", "", "Support: fixed (A=3), pin (A=2), roller (A=1) or clamp = sliding clamp (A=2)")
    angle: float = Input(0.0, "deg", "Free direction of a roller / sliding clamp (0 = horizontal, 90 = vertical)")


def _example_nodes() -> list[NodeInput]:
    # Two-hinge continuous beam: pin at 0, roller at 4, hinges at 7 and 9, pin at 14
    spec = [("A", 0, "rigid"), ("B", 4, "rigid"), ("G1", 7, "hinge"), ("G2", 9, "hinge"), ("C", 14, "rigid")]
    return [NodeInput(id=i, x=x, y=0.0, joint=j) for i, x, j in spec]


def _example_members() -> list[MemberInput]:
    return [MemberInput(id=f"m{i + 1}", a=a, b=b) for i, (a, b) in
            enumerate([("A", "B"), ("B", "G1"), ("G1", "G2"), ("G2", "C")])]


def _example_supports() -> list[SupportInput]:
    return [SupportInput(node="A", kind="pin"), SupportInput(node="B", kind="roller", angle=0.0),
            SupportInput(node="C", kind="pin")]


class PolePlanInputs(BaseModel):
    nodes: list[NodeInput] = Field(default_factory=_example_nodes, description="Nodes with position and joint type")
    members: list[MemberInput] = Field(default_factory=_example_members, description="Members between two nodes")
    supports: list[SupportInput] = Field(default_factory=_example_supports, description="Supports at nodes")

    @model_validator(mode="after")
    def _validate(self) -> "PolePlanInputs":
        if not self.nodes or not self.members:
            raise ValueError("The model needs at least one member and its nodes")
        node_ids = [n.id for n in self.nodes]
        if len(set(node_ids)) != len(node_ids):
            dup = sorted({i for i in node_ids if node_ids.count(i) > 1})
            raise ValueError(f"Duplicate node ids: {dup}")
        member_ids = [m.id for m in self.members]
        if len(set(member_ids)) != len(member_ids):
            dup = sorted({i for i in member_ids if member_ids.count(i) > 1})
            raise ValueError(f"Duplicate member ids: {dup}")
        pos = {n.id: (n.x, n.y) for n in self.nodes}
        at_node: dict[str, list[tuple[str, str]]] = {i: [] for i in node_ids}  # node -> [(member id, other end)]
        for m in self.members:
            for end in (m.a, m.b):
                if end not in pos:
                    raise ValueError(f"Member {m.id!r} refers to unknown node {end!r}")
            if m.a == m.b or math.hypot(pos[m.a][0] - pos[m.b][0], pos[m.a][1] - pos[m.b][1]) < 1e-12:
                raise ValueError(f"Member {m.id!r} has zero length")
            at_node[m.a].append((m.id, m.b))
            at_node[m.b].append((m.id, m.a))
        for n in self.nodes:
            if not at_node[n.id]:
                raise ValueError(f"Node {n.id!r} has no member")
            if n.joint in ("sleeve", "shear"):
                ends = at_node[n.id]
                if len(ends) != 2:
                    raise ValueError(f"{n.joint.capitalize()} node {n.id!r} needs exactly two members, found {len(ends)}")
                d1 = np.subtract(pos[ends[0][1]], (n.x, n.y))
                d2 = np.subtract(pos[ends[1][1]], (n.x, n.y))
                cross = float(d1[0] * d2[1] - d1[1] * d2[0]) / (np.linalg.norm(d1) * np.linalg.norm(d2))
                if abs(cross) > 1e-6 or float(d1 @ d2) > 0:
                    raise ValueError(f"{n.joint.capitalize()} node {n.id!r}: the two members must be collinear "
                                     "and lie on opposite sides of the node")
        joint_of = {n.id: n.joint for n in self.nodes}
        for s in self.supports:
            if s.node not in pos:
                raise ValueError(f"Support refers to unknown node {s.node!r}")
            if joint_of[s.node] in ("sleeve", "shear"):
                raise ValueError(f"Node {s.node!r} is a {joint_of[s.node]} joint: place the support on a neighbouring node")
        return self


# ---------------- system: bodies, joints, supports, counting ----------------

@dataclass
class Body:
    id: int                      # 1-based
    members: list[int]           # member indices
    member_ids: list[str]
    nodes: list[str]             # ids of the nodes the body touches
    label: tuple[float, float]   # a point near the body's members, for drawing its number


@dataclass
class Joint:
    kind: str                    # "hinge" | "sleeve" | "shear"
    node: str
    x: float
    y: float
    bodies: list[int]            # body ids meeting here (≥ 2)
    axis: tuple[float, float] | None = None   # unit member direction (sleeve / shear)


@dataclass
class SupportRef:
    node: str
    kind: str
    angle: float                 # degrees
    x: float
    y: float
    bodies: list[int]            # body ids carrying the support point (a hinge: all bodies meeting there)


@dataclass
class Displacements:
    """Exact small-displacement result. ``mode`` quantities belong to the first nullspace vector."""
    dof: int
    body_motion: list[tuple[float, float, float]] = field(default_factory=list)   # per body (u, v, θ)
    node_disp: dict[str, tuple[float, float]] = field(default_factory=dict)

    @property
    def movable(self) -> bool:
        return self.dof > 0


def _nullspace(a: np.ndarray) -> np.ndarray:
    """Orthonormal basis of the nullspace of ``a`` (columns)."""
    n = a.shape[1]
    if a.shape[0] == 0:
        return np.eye(n)
    _, s, vt = np.linalg.svd(a, full_matrices=True)
    smax = s[0] if s.size else 0.0
    rank = int(np.sum(s > RANK_RTOL * smax)) if smax > 0 else 0
    return vt[rank:].T


class System:
    """Bodies, joints, supports and the counting criterion of a validated :class:`PolePlanInputs`."""

    def __init__(self, inp: PolePlanInputs):
        self.inp = inp
        self.nodes = {n.id: n for n in inp.nodes}
        self.node_order = [n.id for n in inp.nodes]
        self.at_node: dict[str, list[int]] = {i: [] for i in self.node_order}
        for k, m in enumerate(inp.members):
            self.at_node[m.a].append(k)
            self.at_node[m.b].append(k)
        xs = [n.x for n in inp.nodes]
        ys = [n.y for n in inp.nodes]
        self.size = max(math.hypot(max(xs) - min(xs), max(ys) - min(ys)), 1e-9)
        self.axis: dict[str, tuple[float, float]] = {}
        for nid, n in self.nodes.items():
            if n.joint in ("sleeve", "shear"):
                m = inp.members[self.at_node[nid][0]]
                other = self.nodes[m.b if m.a == nid else m.a]
                d = np.array([other.x - n.x, other.y - n.y])
                d /= np.linalg.norm(d)
                self.axis[nid] = (float(d[0]), float(d[1]))
        self._find_bodies()
        self._joints_and_supports()
        self._count()
        self.displacements = self._solve()

    # ----- bodies -----

    def _find_bodies(self) -> None:
        inp = self.inp
        nm = len(inp.members)
        parent = list(range(nm))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for nid, ms in self.at_node.items():
            if self.nodes[nid].joint == "rigid":
                for m in ms[1:]:
                    parent[find(m)] = find(ms[0])
        # welded groups numbered by smallest member index
        gid: dict[int, int] = {}
        member_group = []
        for k in range(nm):
            member_group.append(gid.setdefault(find(k), len(gid)))
        ng = len(gid)
        self.n_groups = ng
        # triangulated truss parts: merge groups that move identically in every mode of the free system
        null = _nullspace(self._matrix(member_group, ng, with_supports=False))
        rows = null[:3 * ng]
        uv_scale = max(float(np.abs(rows[0::3]).max()), float(np.abs(rows[1::3]).max()), 1e-12)
        th_scale = max(float(np.abs(rows[2::3]).max()), 1e-12)
        reps: list[int] = []
        body_of_group: list[int] = []
        for g in range(ng):
            for bi, r in enumerate(reps):
                du = max(np.abs(rows[3 * g:3 * g + 2] - rows[3 * r:3 * r + 2]).max(), 0.0)
                dt = abs(rows[3 * g + 2] - rows[3 * r + 2]).max()
                if du <= MERGE_RTOL * uv_scale and dt <= MERGE_RTOL * th_scale:
                    body_of_group.append(bi)
                    break
            else:
                body_of_group.append(len(reps))
                reps.append(g)
        self.member_body = [body_of_group[g] for g in member_group]   # 0-based body index per member
        nb = len(reps)
        self.bodies: list[Body] = []
        for bi in range(nb):
            ms = [k for k in range(nm) if self.member_body[k] == bi]
            nodes = sorted({e for k in ms for e in (inp.members[k].a, inp.members[k].b)},
                           key=self.node_order.index)
            wsum = cx = cy = 0.0
            for k in ms:
                a, b = self.nodes[inp.members[k].a], self.nodes[inp.members[k].b]
                length = math.hypot(b.x - a.x, b.y - a.y)
                wsum += length
                cx += length * (a.x + b.x) / 2
                cy += length * (a.y + b.y) / 2
            self.bodies.append(Body(bi + 1, ms, [inp.members[k].id for k in ms], nodes, (cx / wsum, cy / wsum)))

    def node_bodies(self, nid: str, member_body: list[int] | None = None) -> list[int]:
        """Sorted 0-based body indices meeting at a node."""
        mb = self.member_body if member_body is None else member_body
        return sorted({mb[k] for k in self.at_node[nid]})

    # ----- joints, supports, counting -----

    def _joints_and_supports(self) -> None:
        self.joints: list[Joint] = []
        for nid in self.node_order:
            n = self.nodes[nid]
            bodies = [b + 1 for b in self.node_bodies(nid)]
            if n.joint != "rigid" and len(bodies) >= 2:
                self.joints.append(Joint(n.joint, nid, n.x, n.y, bodies, self.axis.get(nid)))
        self.supports: list[SupportRef] = []
        for s in self.inp.supports:
            n = self.nodes[s.node]
            bodies = [b + 1 for b in self.node_bodies(s.node)]
            if s.kind in ("fixed", "clamp") and len(bodies) > 1:
                raise ValueError(f"A {s.kind} support at hinge node {s.node!r} joining several bodies is ambiguous: "
                                 "use a pin there or move the support to a member end")
            self.supports.append(SupportRef(s.node, s.kind, s.angle, n.x, n.y, bodies))

    def _count(self) -> None:
        self.k = len(self.bodies)
        self.A = sum(SUPPORT_REACTIONS[s.kind] for s in self.inp.supports)
        z = 0
        for j in self.joints:
            z += 2 * (len(j.bodies) - 1) if j.kind == "hinge" else 2
        self.z = z
        self.U = (self.A + self.z) - 3 * self.k
        self.counting = f"U = (A + z) − 3k = ({self.A} + {self.z}) − 3·{self.k} = {self.U}"

    # ----- exact analysis -----

    def _matrix(self, member_body: list[int], nb: int, with_supports: bool) -> np.ndarray:
        hinge_nodes = [i for i in self.node_order if self.nodes[i].joint == "hinge"]
        hcol = {nid: 3 * nb + 2 * i for i, nid in enumerate(hinge_nodes)}
        ncol = 3 * nb + 2 * len(hinge_nodes)
        rows: list[np.ndarray] = []

        def vel(b: int, px: float, py: float) -> tuple[np.ndarray, np.ndarray]:
            rx, ry = np.zeros(ncol), np.zeros(ncol)
            rx[3 * b], rx[3 * b + 2] = 1.0, -py
            ry[3 * b + 1], ry[3 * b + 2] = 1.0, px
            return rx, ry

        def unit(col: int) -> np.ndarray:
            e = np.zeros(ncol)
            e[col] = 1.0
            return e

        for nid in self.node_order:
            n = self.nodes[nid]
            bodies = self.node_bodies(nid, member_body)
            if n.joint == "hinge":
                for b in bodies:
                    rx, ry = vel(b, n.x, n.y)
                    rows.append(rx - unit(hcol[nid]))
                    rows.append(ry - unit(hcol[nid] + 1))
            elif n.joint in ("sleeve", "shear") and len(bodies) == 2:
                i, j = bodies
                rxi, ryi = vel(i, n.x, n.y)
                rxj, ryj = vel(j, n.x, n.y)
                tx, ty = self.axis[nid]
                dx, dy = (-ty, tx) if n.joint == "sleeve" else (tx, ty)   # relative displacement that must vanish
                th = np.zeros(ncol)
                th[3 * i + 2], th[3 * j + 2] = 1.0, -1.0
                rows.append(th)
                rows.append((rxi - rxj) * dx + (ryi - ryj) * dy)
        if with_supports:
            for s in self.inp.supports:
                n = self.nodes[s.node]
                bodies = self.node_bodies(s.node, member_body)
                if n.joint == "hinge":
                    wx, wy = unit(hcol[s.node]), unit(hcol[s.node] + 1)
                else:
                    wx, wy = vel(bodies[0], n.x, n.y)
                if s.kind in ("pin", "fixed"):
                    rows += [wx, wy]
                else:
                    a = math.radians(s.angle)
                    rows.append(-math.sin(a) * wx + math.cos(a) * wy)
                if s.kind in ("fixed", "clamp"):
                    rows.append(unit(3 * bodies[0] + 2))
        return np.array(rows) if rows else np.zeros((0, ncol))

    def _solve(self) -> Displacements:
        nb = len(self.bodies)
        null = _nullspace(self._matrix(self.member_body, nb, with_supports=True))
        dof = null.shape[1]
        if dof == 0:
            return Displacements(0)
        vec = null[:, 0]
        motion = [tuple(float(c) for c in vec[3 * b:3 * b + 3]) for b in range(nb)]

        def disp(b: int, x: float, y: float) -> tuple[float, float]:
            u, v, th = motion[b]
            return u - th * y, v + th * x

        nd = {nid: disp(self.node_bodies(nid)[0], self.nodes[nid].x, self.nodes[nid].y) for nid in self.node_order}
        peak = max(max(abs(d[0]), abs(d[1])) for d in nd.values())
        scale = 1.0 / peak if peak > 1e-14 else 1.0
        big = max((c for d in nd.values() for c in d), key=abs, default=1.0)
        if big < 0:
            scale = -scale
        def clean(x: float) -> float:
            x *= scale
            return 0.0 if abs(x) < 1e-12 else x   # also drops the sign of -0.0

        motion = [(clean(u), clean(v), clean(th)) for u, v, th in motion]
        nd = {k: (clean(d[0]), clean(d[1])) for k, d in nd.items()}
        return Displacements(dof, motion, nd)


def build_system(inp: PolePlanInputs) -> System:
    return System(inp)
