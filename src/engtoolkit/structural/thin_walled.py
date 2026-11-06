"""
Shear flow and shear centre of thin-walled cross-sections (open, branched, closed, multi-cell).

Procedure and notation of the RWTH OLS formulary (§2):
- x1 beam axis; section axes x2 (horizontal, right) and x3 (vertical, pointing DOWN).
- The section is a set of straight walls (mid-lines) between nodes; wall i→j defines s and the sign of t.
- h wall thickness, t shear flow [N/m], Q2/Q3 shear forces (positive in +x2/+x3), M_t torque about +x1
  (right-handed x1, x2, x3: positive from x2 towards x3).
- S2 = ∫x3 h ds, S3 = ∫x2 h ds, J22 = ∫x3² h ds, J33 = ∫x2² h ds, J23 = ∫x2 x3 h ds, all about the
  centroid along the mid-lines (thin-walled: no h³ own terms).

Steps: cut each cell open → t' from the unsymmetric bending formula and node continuity; close each cell
with a circulating t0 from ϑ' = 0 (∮ t/(G h) ds = 0 per cell); shear centre SC from moment equilibrium;
the torque about SC is carried by Bredt flows (closed) or Saint-Venant shear (open, reported separately).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from engtoolkit.core.results import Result, rfield


@dataclass
class ShearFlowResult(Result):
    A: float = rfield("m^2", "Area A = Σ h l")
    x2S: float = rfield("m", "Centroid x2S")
    x3S: float = rfield("m", "Centroid x3S")
    J22: float = rfield("m^4", "J22 = ∫x3² h ds")
    J33: float = rfield("m^4", "J33 = ∫x2² h ds")
    J23: float = rfield("m^4", "J23 = ∫x2 x3 h ds")
    phi: float = rfield("rad", "Principal angle φ, tan 2φ = −2 J23/(J22 − J33)")
    phi_deg: float = rfield("deg", "Principal angle φ")
    x2_SC: float = rfield("m", "Shear centre x2")
    x3_SC: float = rfield("m", "Shear centre x3")
    e2: float = rfield("m", "Shear centre offset e2 = x2_SC − x2S")
    e3: float = rfield("m", "Shear centre offset e3 = x3_SC − x3S")
    n_cells: int = rfield("", "Number of closed cells")
    torque_SC: float = rfield("N·m", "Torque about the shear centre")
    J_T: float = rfield("m^4", "Torsion constant J_T (Bredt if closed, Σ l h³/3 if open)")
    twist_rate: float = rfield("rad/m", "Rate of twist ϑ' from the torque")
    t_max: float = rfield("N/m", "Max |shear flow t|")
    t_max_wall: int = rfield("", "Wall of max |t|")
    t_max_s: float = rfield("m", "Position s of max |t| along that wall")
    tau_max: float = rfield("Pa", "Max shear stress |t/h|")
    tau_torsion_open: float = rfield("Pa", "Open section: Saint-Venant τ_max = M_t h_max / J_T (not in t)",
                                     default=math.nan)
    note: str = rfield("", "Note", default="")
    A_cell: list = rfield("m^2", "Enclosed area per cell", default_factory=list, summary=False)
    cut_walls: list = rfield("", "Walls cut open (one per cell, cut at the wall start)",
                             default_factory=list, summary=False)
    cells: list = rfield("", "Cells: node loop, walls, signs, A, t0, t_torque", default_factory=list, summary=False)
    steps: list = rfield("", "Formulary steps", default_factory=list, summary=False)
    walls: list = rfield("", "Per-wall plot data", default_factory=list, summary=False)


def _wall_tuples(walls) -> list[tuple[int, int, float, float]]:
    out = []
    for w in walls:
        if isinstance(w, dict):
            out.append((w["i"], w["j"], w["h"], w.get("G", 81e9)))
        else:
            w = tuple(w)
            out.append((w[0], w[1], w[2], w[3] if len(w) > 3 else 81e9))
    return out


def _validate(P: np.ndarray, walls) -> None:
    if P.ndim != 2 or P.shape[1] != 2 or len(P) < 2:
        raise ValueError("Need at least 2 nodes, each with (x2, x3)")
    if not walls:
        raise ValueError("Need at least one wall")
    N = len(P)
    scale = float(np.ptp(P, axis=0).max()) or 1.0
    seen = set()
    parent = list(range(N))

    def root(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for k, (i, j, h, G) in enumerate(walls):
        if int(i) != i or int(j) != j or not (0 <= i < N and 0 <= j < N):
            raise ValueError(f"Wall {k}: node index out of range (0..{N - 1})")
        if i == j or np.hypot(*(P[j] - P[i])) <= 1e-12 * scale:
            raise ValueError(f"Wall {k}: zero length (nodes {i} and {j} coincide)")
        key = (min(i, j), max(i, j))
        if key in seen:
            raise ValueError(f"Wall {k}: duplicate wall between nodes {i} and {j}")
        seen.add(key)
        if not h > 0:
            raise ValueError(f"Wall {k}: thickness h must be > 0")
        if not G > 0:
            raise ValueError(f"Wall {k}: shear modulus G must be > 0")
        parent[root(int(i))] = root(int(j))
    if len({root(n) for n in range(N)}) > 1:
        raise ValueError("Section is not connected: every node must be joined to the others by walls")


def _faces(P, wi, wj):
    """Interior faces of the planar wall graph: (node loop, wall list, sign list, signed area)."""
    adj: dict[int, list] = {n: [] for n in range(len(P))}
    for w, (i, j) in enumerate(zip(wi, wj)):
        d = P[j] - P[i]
        adj[i].append((math.atan2(d[1], d[0]), j, w))
        adj[j].append((math.atan2(-d[1], -d[0]), i, w))
    pos = {}
    for n in adj:
        adj[n].sort()
        for k, (_, _, w) in enumerate(adj[n]):
            pos[(n, w)] = k
    seen = set()
    faces = []
    for start in [(n, w) for n in adj for (_, _, w) in adj[n]]:
        if start in seen:
            continue
        walk = []
        u, w = start
        while (u, w) not in seen:
            seen.add((u, w))
            v = wj[w] if u == wi[w] else wi[w]
            walk.append((u, v, w))
            nb = adj[v]
            u, w = v, nb[(pos[(v, w)] - 1) % len(nb)][2]  # clockwise-next: face on the left
        area = 0.5 * sum(P[u, 0] * P[v, 1] - P[v, 0] * P[u, 1] for u, v, _ in walk)
        net: dict[int, int] = {}
        for u, _, w in walk:
            net[w] = net.get(w, 0) + (1 if u == wi[w] else -1)
        loop = [(u, w) for u, _, w in walk if net[w] != 0]  # drop branches walked both ways
        faces.append(([u for u, _ in loop], [w for _, w in loop], [net[w] for _, w in loop], area))
    return faces


def _integral(c, a, b, l):
    """∫0^l (c + a s + b s²) ds per wall."""
    return c * l + a * l**2 / 2 + b * l**3 / 3


def shear_flow(nodes, walls, Q2: float = 0.0, Q3: float = 1000.0, Mt: float = 0.0,
               load_point: tuple[float, float] | None = None, n_samples: int = 41) -> ShearFlowResult:
    """
    Shear flow t(s) and shear centre of a thin-walled section.

    ``nodes``: [(x2, x3), ...] in m (x3 down). ``walls``: [(i, j, h[, G]), ...] or dicts with keys i, j, h, G.
    ``load_point``: (a2, a3) on the load line of (Q2, Q3); None = load through the shear centre.
    ``Mt``: torque about +x1 (positive from x2 towards x3).
    """
    P = np.asarray(nodes, dtype=float)
    walls = _wall_tuples(walls)
    _validate(P, walls)
    N, W = len(P), len(walls)
    wi = np.array([int(w[0]) for w in walls])
    wj = np.array([int(w[1]) for w in walls])
    h = np.array([float(w[2]) for w in walls])
    G = np.array([float(w[3]) for w in walls])
    p, q = P[wi], P[wj]
    l = np.hypot(*(q - p).T)
    e = (q - p) / l[:, None]

    # 1. properties along the mid-lines
    A = float(np.sum(h * l))
    x2S, x3S = (np.sum((h * l)[:, None] * (p + q) / 2, axis=0) / A).tolist()
    a2, a3 = p[:, 0] - x2S, p[:, 1] - x3S
    b2, b3 = q[:, 0] - x2S, q[:, 1] - x3S
    J22 = float(np.sum(h * l * (a3**2 + a3 * b3 + b3**2) / 3))
    J33 = float(np.sum(h * l * (a2**2 + a2 * b2 + b2**2) / 3))
    J23 = float(np.sum(h * l * (2 * a2 * a3 + a2 * b3 + b2 * a3 + 2 * b2 * b3) / 6))
    D = J22 * J33 - J23**2
    if D <= 1e-12 * (J22 + J33)**2:
        raise ValueError("Singular section (J22 J33 − J23² = 0): all walls lie on one line")
    phi = 0.5 * math.atan2(-2 * J23, J22 - J33)

    # cells: faces of the planar wall graph, positive circulation from x2 towards x3
    n_cells = W - N + 1
    cells = []
    if n_cells:
        scale = float(np.ptp(P, axis=0).max())
        cells = [f for f in _faces(P, wi.tolist(), wj.tolist()) if f[3] > 1e-9 * scale**2]
        if len(cells) != n_cells:
            raise ValueError("Walls cross or overlap without a shared node: put a node at every junction")
    C = np.zeros((n_cells, W))
    for k, (_, ws, signs, _) in enumerate(cells):
        C[k, ws] = signs
    A_cell = np.array([f[3] for f in cells])

    # cut walls: walls outside a spanning tree (one per independent cell), cut at their start
    tree, reached, frontier = set(), {0}, [0]
    while frontier:
        n = frontier.pop()
        for w in range(W):
            if n in (wi[w], wj[w]):
                m = wj[w] if n == wi[w] else wi[w]
                if m not in reached:
                    reached.add(m)
                    tree.add(w)
                    frontier.append(m)
    cut = [w for w in range(W) if w not in tree]

    # 2. cut-open static moments S2, S3 as per-wall polynomials c + α s + β s², continuous at nodes
    B = np.zeros((N + len(cut), W))
    B[wi, np.arange(W)] -= 1
    B[wj, np.arange(W)] += 1
    for r, w in enumerate(cut):
        B[N + r, w] = 1.0

    def cut_open(y0, y1):
        al, be = h * y0, h * (y1 - y0) / (2 * l)
        F = h * l * (y0 + y1) / 2
        rhs = np.zeros(N + len(cut))
        np.add.at(rhs, wj, -F)
        c = np.linalg.lstsq(B, rhs, rcond=None)[0]
        return np.array([c, al, be])

    S2 = cut_open(a3, b3)
    S3 = cut_open(a2, b2)
    Kw = l / (G * h)
    K = (C * Kw) @ C.T
    rho = p[:, 0] * e[:, 1] - p[:, 1] * e[:, 0]  # lever arm of each wall about the origin

    def flow(Q2_, Q3_):
        """t' (cut, polynomial) and t0 per cell for shear (Q2_, Q3_) through the shear centre."""
        tc = -((Q3_ * J33 - Q2_ * J23) * S2 + (Q2_ * J22 - Q3_ * J23) * S3) / D
        t0 = -np.linalg.solve(K, C @ (_integral(*tc, l) / (G * h))) if n_cells else np.zeros(0)
        return tc, t0

    def moment(tc, t0):
        return float(np.sum(rho * (_integral(*tc, l) + (C.T @ t0) * l)))

    # 3. shear centre from moment equilibrium for unit Q3 (x2) and unit Q2 (x3)
    tc3, t03 = flow(0.0, 1.0)
    x2_SC = moment(tc3, t03)
    x3_SC = -moment(*flow(1.0, 0.0))
    e1 = moment(tc3, np.zeros(n_cells)) - x2S  # cut-open SC estimate

    # 4. torque about SC, carried by Bredt flows (closed) or Saint-Venant shear (open)
    T = Mt
    if load_point is not None:
        T += (load_point[0] - x2_SC) * Q3 - (load_point[1] - x3_SC) * Q2
    note = ""
    tau_open = math.nan
    tau_cell = np.zeros(n_cells)
    if n_cells:
        J_T = float(2 * A_cell @ np.linalg.solve((C * (l / h)) @ C.T, 2 * A_cell))
        Kinv2A = np.linalg.solve(K, 2 * A_cell)
        twist_rate = T / float(2 * A_cell @ Kinv2A)
        tau_cell = twist_rate * Kinv2A
    else:
        J_T = float(np.sum(l * h**3 / 3))
        twist_rate = T / float(np.sum(G * l * h**3 / 3))
        tau_open = abs(T) * float(h.max()) / J_T
        if T:
            note = ("Open section: the torque about the shear centre is carried by Saint-Venant shear "
                    "(τ = M_t h / J_T, see tau_torsion_open); it is not part of t.")

    tc, t0 = flow(Q2, Q3)
    t0w, ttw = C.T @ t0, C.T @ tau_cell
    tot = tc + np.array([t0w + ttw, np.zeros(W), np.zeros(W)])

    # 5. per-wall samples, maxima, steps
    t_max, t_max_wall, t_max_s, tau_max = 0.0, 0, 0.0, 0.0
    wall_data = []
    for w in range(W):
        s = np.linspace(0.0, l[w], n_samples)
        cands = [s]
        if tot[2, w]:
            sv = -tot[1, w] / (2 * tot[2, w])
            if 0 < sv < l[w]:
                cands.append(np.array([sv]))
        sc = np.concatenate(cands)
        tv = np.abs(tot[0, w] + tot[1, w] * sc + tot[2, w] * sc**2)
        k = int(np.argmax(tv))
        if tv[k] > t_max:
            t_max, t_max_wall, t_max_s = float(tv[k]), w, float(sc[k])
        tau_max = max(tau_max, float(tv[k] / h[w]))

        def ev(cf, s=s, w=w):
            return (cf[0, w] + cf[1, w] * s + cf[2, w] * s**2).tolist()

        t_total = np.array(ev(tot))
        wall_data.append({
            "wall": w, "i": int(wi[w]), "j": int(wj[w]), "h": float(h[w]), "G": float(G[w]),
            "length": float(l[w]), "s": s.tolist(),
            "x2": (p[w, 0] + e[w, 0] * s).tolist(), "x3": (p[w, 1] + e[w, 1] * s).tolist(),
            "t_cut": ev(tc), "t0": [float(t0w[w])] * n_samples, "t_torque": [float(ttw[w])] * n_samples,
            "t_total": t_total.tolist(), "tau": (t_total / h[w]).tolist(), "S2": ev(S2), "S3": ev(S3),
        })

    deg = np.bincount(np.concatenate([wi, wj]), minlength=N)
    n_in = np.bincount(wj, minlength=N)
    tiny = 1e-12 * max(abs(J22), abs(J33)) ** 0.75
    steps = []
    for w in range(W):
        i, j = int(wi[w]), int(wj[w])
        if abs(S2[0, w]) > tiny and not (deg[i] == 2 and n_in[i] == 1):
            steps.append({"label": f"S2, wall {w} at node {i} (start)", "value": float(S2[0, w]), "unit": "m^3"})
        steps.append({"label": f"S2, wall {w} at node {j} (end)",
                      "value": float(S2[0, w] + h[w] * l[w] * (a3[w] + b3[w]) / 2), "unit": "m^3"})
    steps += [{"label": "J22 = ∫x3² h ds", "value": J22, "unit": "m^4"},
              {"label": "J33 = ∫x2² h ds", "value": J33, "unit": "m^4"},
              {"label": "J23 = ∫x2 x3 h ds", "value": J23, "unit": "m^4"},
              {"label": "e1 (cut-open shear centre, x2 from centroid)", "value": e1, "unit": "m"}]
    for k in range(n_cells):
        steps.append({"label": f"A_cell {k}", "value": float(A_cell[k]), "unit": "m^2"})
        steps.append({"label": f"t0 cell {k} (closing flow, load at SC)", "value": float(t0[k]), "unit": "N/m"})

    return ShearFlowResult(
        A=A, x2S=x2S, x3S=x3S, J22=J22, J33=J33, J23=J23, phi=phi, phi_deg=math.degrees(phi),
        x2_SC=x2_SC, x3_SC=x3_SC, e2=x2_SC - x2S, e3=x3_SC - x3S, n_cells=n_cells, torque_SC=T,
        J_T=J_T, twist_rate=twist_rate, t_max=t_max, t_max_wall=t_max_wall, t_max_s=t_max_s, tau_max=tau_max,
        tau_torsion_open=tau_open, note=note, A_cell=A_cell.tolist(), cut_walls=cut,
        cells=[{"nodes": [int(n) for n in f[0]], "walls": [int(w) for w in f[1]], "signs": [int(s) for s in f[2]],
                "A": float(f[3]), "t0": float(t0[k]), "t_torque": float(tau_cell[k])}
               for k, f in enumerate(cells)],
        steps=steps, walls=wall_data,
    )


def _formulary_single_cell_x2_sc(points, h, G=None) -> float:
    """
    Formulary closed form for one closed cell symmetric about x2 (J23 = 0), load Q3:
    e = e1 + 2 (A/J22) ∮ S2/(G h) ds / ∮ ds/(G h), with S2 from a cut at points[0] and e1 the
    cut-open shear centre. Edge k runs points[k] → points[k+1]. Returns x2 of SC (cross-check only).
    """
    P = np.asarray(points, dtype=float)
    Q = np.roll(P, -1, axis=0)
    h = np.asarray(h, dtype=float)
    G = np.ones(len(P)) if G is None else np.asarray(G, dtype=float)
    l = np.hypot(*(Q - P).T)
    x3S = np.sum(h * l * (P[:, 1] + Q[:, 1]) / 2) / np.sum(h * l)
    a, b = P[:, 1] - x3S, Q[:, 1] - x3S
    J22 = np.sum(h * l * (a**2 + a * b + b**2) / 3)
    S2_0 = np.concatenate([[0.0], np.cumsum(h * l * (a + b) / 2)[:-1]])
    int_S2 = S2_0 * l + h * (a * l**2 / 2 + (b - a) * l**2 / 6)
    e = (Q - P) / l[:, None]
    rho = P[:, 0] * e[:, 1] - P[:, 1] * e[:, 0]
    e1 = float(np.sum(rho * (-int_S2 / J22)))
    A = 0.5 * np.sum(P[:, 0] * Q[:, 1] - Q[:, 0] * P[:, 1])
    return e1 + 2 * A / J22 * np.sum(int_S2 / (G * h)) / np.sum(l / (G * h))


@dataclass
class SectorialResult(Result):
    C_T: float = rfield("m^6", "Warping constant C_T = ∫ω² h ds")
    omega_max: float = rfield("m^2", "Max |ω| (principal sectorial coordinate)")
    omega_max_wall: int = rfield("", "Wall of max |ω|")
    omega_max_s: float = rfield("m", "Position s of max |ω| along that wall")
    x2_SC: float = rfield("m", "Shear centre x2 (pole)")
    x3_SC: float = rfield("m", "Shear centre x3 (pole)")
    omega_nodes: list = rfield("m^2", "ω at each node", default_factory=list, summary=False)
    walls: list = rfield("", "Per-wall samples: s, x2, x3, omega", default_factory=list, summary=False)


def sectorial(nodes, walls, n_samples: int = 21) -> SectorialResult:
    """
    Principal sectorial coordinate ω(s) and warping constant C_T of an OPEN thin-walled section.

    Formulary §3.2: pole at the shear centre P, dω = r_t ds with r_t the lever arm of the wall tangent about P
    (dω = (x2 − x2P) dx3 − (x3 − x3P) dx2), normalised so ∫ω h ds = 0. With the pole at the shear centre
    ∫ω x2 h ds = ∫ω x3 h ds = 0 as well. C_T = ∫ω² h ds along the mid-lines (ω is linear on each wall).
    Inputs as for :func:`shear_flow`; raises ValueError for closed sections (n_cells ≥ 1).
    """
    P = np.asarray(nodes, dtype=float)
    wt = _wall_tuples(walls)
    _validate(P, wt)
    N, W = len(P), len(wt)
    if W - N + 1 != 0:
        raise ValueError("sectorial() needs an open section (no closed cells)")
    sc = shear_flow(P.tolist(), wt, Q2=0.0, Q3=0.0)
    pole = np.array([sc.x2_SC, sc.x3_SC])
    wi = [int(w[0]) for w in wt]
    wj = [int(w[1]) for w in wt]
    h = np.array([float(w[2]) for w in wt])
    l = np.hypot(*(P[wj] - P[wi]).T)
    # ω along the tree from node 0 (dω over wall i→j = (p_i − P) × (p_j − p_i))
    d_omega = [float((P[i, 0] - pole[0]) * (P[j, 1] - P[i, 1]) - (P[i, 1] - pole[1]) * (P[j, 0] - P[i, 0]))
               for i, j in zip(wi, wj)]
    om = np.full(N, np.nan)
    om[0] = 0.0
    frontier = [0]
    while frontier:
        n = frontier.pop()
        for w in range(W):
            for a, b, sgn in ((wi[w], wj[w], 1.0), (wj[w], wi[w], -1.0)):
                if a == n and np.isnan(om[b]):
                    om[b] = om[a] + sgn * d_omega[w]
                    frontier.append(b)
    oa, ob = om[wi], om[wj]
    A = float(np.sum(h * l))
    om = om - float(np.sum(h * l * (oa + ob) / 2)) / A
    oa, ob = om[wi], om[wj]
    C_T = float(np.sum(h * l * (oa**2 + oa * ob + ob**2) / 3))
    k = int(np.argmax(np.abs(om)))
    om_max = float(abs(om[k]))
    # the max of a linear ω is at a node; report the first wall touching it
    w_max = next(w for w in range(W) if k in (wi[w], wj[w]))
    s_max = 0.0 if wi[w_max] == k else float(l[w_max])
    wall_data = []
    for w in range(W):
        s = np.linspace(0.0, l[w], n_samples)
        e = (P[wj[w]] - P[wi[w]]) / l[w]
        wall_data.append({"wall": w, "i": wi[w], "j": wj[w], "s": s.tolist(),
                          "x2": (P[wi[w], 0] + e[0] * s).tolist(), "x3": (P[wi[w], 1] + e[1] * s).tolist(),
                          "omega": (oa[w] + (ob[w] - oa[w]) * s / l[w]).tolist()})
    return SectorialResult(C_T=C_T, omega_max=om_max, omega_max_wall=w_max, omega_max_s=s_max,
                           x2_SC=float(pole[0]), x3_SC=float(pole[1]), omega_nodes=om.tolist(), walls=wall_data)
