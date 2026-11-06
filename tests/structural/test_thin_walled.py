import math

import numpy as np
import pytest

from engtoolkit.structural.thin_walled import _formulary_single_cell_x2_sc, shear_flow


def _simpson(y, s):
    # exact for the quadratic t(s) on an odd number of equal steps
    y, ds = np.asarray(y), s[1] - s[0]
    return ds / 3 * (y[0] + y[-1] + 4 * y[1:-1:2].sum() + 2 * y[2:-1:2].sum())


def _resultants(r, key="t_total"):
    """Force (R2, R3) and moment about the origin of the flow `key`."""
    R2 = R3 = M = 0.0
    for w in r.walls:
        s = np.asarray(w["s"])
        F = _simpson(w[key], s)
        e2, e3 = (w["x2"][-1] - w["x2"][0]) / w["length"], (w["x3"][-1] - w["x3"][0]) / w["length"]
        R2, R3 = R2 + F * e2, R3 + F * e3
        M += (w["x2"][0] * e3 - w["x3"][0] * e2) * F
    return R2, R3, M


def _node_balance(r, n_nodes):
    bal = np.zeros(n_nodes)
    for w in r.walls:
        bal[w["j"]] += w["t_total"][-1]
        bal[w["i"]] -= w["t_total"][0]
    return bal


def _cell_twist(r, k):
    """∮ t/(G h) ds / (2 A) for cell k = rate of twist ϑ'."""
    cell = r.cells[k]
    tot = sum(sg * _simpson(np.asarray(r.walls[w]["t_total"]) / (r.walls[w]["G"] * r.walls[w]["h"]),
                            np.asarray(r.walls[w]["s"]))
              for w, sg in zip(cell["walls"], cell["signs"]))
    return tot / (2 * cell["A"])


def _ring(r, n, closed):
    nodes = [(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n)) for k in range(n)]
    walls = [(k, (k + 1) % n, 0.002) for k in range(n)]
    if not closed:  # slit at angle 0: last wall ends on a separate node at the same point
        nodes.append(nodes[0])
        walls[-1] = (n - 1, n, 0.002)
    return nodes, walls


def test_channel_shear_centre_and_web_flow():
    b, d, h, Q = 0.05, 0.1, 0.002, 1000.0
    r = shear_flow([(b, 0), (0, 0), (0, d), (b, d)], [(0, 1, h), (1, 2, h), (2, 3, h)], Q3=Q)
    assert r.n_cells == 0
    assert r.x2_SC == pytest.approx(-3 * b**2 / (6 * b + d), rel=1e-6)  # opposite side to the flanges
    assert r.x3_SC == pytest.approx(d / 2, rel=1e-6)
    J22 = h * d**3 / 12 + 2 * b * h * (d / 2) ** 2
    S2 = b * h * d / 2 + h * (d / 2) * (d / 4)
    web = r.walls[1]
    assert web["t_total"][len(web["s"]) // 2] == pytest.approx(Q * S2 / J22, rel=1e-6)
    assert r.t_max == pytest.approx(Q * S2 / J22, rel=1e-6)


def test_symmetric_i_section():
    b, d, h = 0.1, 0.2, 0.004
    nodes = [(-b / 2, 0), (b / 2, 0), (0, 0), (0, d), (-b / 2, d), (b / 2, d)]
    walls = [(0, 2, h), (1, 2, h), (2, 3, h), (3, 4, h), (3, 5, h)]
    r = shear_flow(nodes, walls, Q2=300.0, Q3=1000.0)
    assert (r.x2_SC, r.x3_SC) == pytest.approx((r.x2S, r.x3S), abs=1e-9)
    assert (r.x2S, r.x3S) == pytest.approx((0, d / 2))
    web = r.walls[2]
    assert _simpson(web["t_total"], np.asarray(web["s"])) == pytest.approx(1000.0, rel=1e-6)
    assert _resultants(r)[:2] == pytest.approx((300.0, 1000.0), rel=1e-6)


def test_equal_angle_shear_centre_at_leg_intersection():
    b, h = 0.06, 0.005
    r = shear_flow([(b, 0), (0, 0), (0, b)], [(0, 1, h), (1, 2, h)], Q2=200.0, Q3=1000.0)
    assert r.J23 != pytest.approx(0)
    assert (r.x2_SC, r.x3_SC) == pytest.approx((0, 0), abs=1e-9)
    assert _resultants(r)[:2] == pytest.approx((200.0, 1000.0), rel=1e-6)


def test_slit_tube_shear_centre_at_2r():
    R = 0.05
    nodes, walls = _ring(R, 400, closed=False)
    r = shear_flow(nodes, walls, Q3=1000.0)
    assert r.n_cells == 0
    assert r.x2_SC == pytest.approx(-2 * R, rel=1e-3)
    assert r.x3_SC == pytest.approx(0, abs=1e-6)


def test_closed_tube():
    R, Q = 0.05, 1000.0
    nodes, walls = _ring(R, 400, closed=True)
    r = shear_flow(nodes, walls, Q3=Q)
    assert r.n_cells == 1
    assert r.t_max == pytest.approx(Q / (math.pi * R), rel=1e-3)
    assert (r.x2_SC, r.x3_SC) == pytest.approx((0, 0), abs=1e-6)
    assert r.A_cell[0] == pytest.approx(math.pi * R**2, rel=1e-3)


def test_symmetric_box():
    b, d = 0.08, 0.12
    nodes = [(0, 0), (b, 0), (b, d), (0, d)]
    walls = [(0, 1, 0.004), (1, 2, 0.002), (2, 3, 0.004), (3, 0, 0.002)]
    r = shear_flow(nodes, walls, Q2=500.0, Q3=1000.0)
    assert (r.x2_SC, r.x3_SC) == pytest.approx((b / 2, d / 2), rel=1e-9)
    assert _cell_twist(r, 0) == pytest.approx(0, abs=1e-15)
    assert len(r.cut_walls) == 1
    assert _resultants(r)[:2] == pytest.approx((500.0, 1000.0), rel=1e-6)


def test_asymmetric_cell_matches_formulary_closed_form():
    # trapezoid symmetric about x2 (J23 = 0), walls of different h and G
    pts = [(0, -0.06), (0.15, -0.03), (0.15, 0.03), (0, 0.06)]
    h = [0.002, 0.003, 0.002, 0.005]
    G = [81e9, 81e9, 81e9, 27e9]
    r = shear_flow(pts, [(k, (k + 1) % 4, h[k], G[k]) for k in range(4)], Q3=1000.0)
    assert r.J23 == pytest.approx(0, abs=1e-15)
    assert r.x2_SC == pytest.approx(_formulary_single_cell_x2_sc(pts, h, G), rel=1e-6)
    # opposite orientation of the walls gives the same shear centre
    rev = shear_flow(pts, [((k + 1) % 4, k, h[k], G[k]) for k in range(4)], Q3=1000.0)
    assert rev.x2_SC == pytest.approx(r.x2_SC, rel=1e-9)


def _two_cell(**kw):
    a, b = 0.1, 0.08
    nodes = [(0, 0), (a, 0), (2.5 * a, 0), (2.5 * a, b), (a, b), (0, b)]
    walls = [(0, 1, 0.003), (1, 2, 0.002), (2, 3, 0.004), (3, 4, 0.002), (4, 5, 0.003), (5, 0, 0.002),
             (1, 4, 0.0015)]
    return nodes, shear_flow(nodes, walls, **kw)


def test_two_cell_box_shear():
    nodes, r = _two_cell(Q2=300.0, Q3=1000.0)
    assert r.n_cells == 2 and len(r.cut_walls) == 2
    assert sum(r.A_cell) == pytest.approx(0.25 * 0.08, rel=1e-9)
    R2, R3, M = _resultants(r)
    assert (R2, R3) == pytest.approx((300.0, 1000.0), rel=1e-6)
    assert M == pytest.approx(r.x2_SC * 1000.0 - r.x3_SC * 300.0, rel=1e-6)
    assert np.abs(_node_balance(r, len(nodes))).max() < 1e-9
    assert [_cell_twist(r, k) for k in range(2)] == pytest.approx([0, 0], abs=1e-15)


def test_two_cell_box_pure_torque():
    nodes, r = _two_cell(Q3=0.0, Mt=500.0)
    rates = [_cell_twist(r, k) for k in range(2)]
    assert rates[0] == pytest.approx(rates[1], rel=1e-9)
    assert rates[0] == pytest.approx(r.twist_rate, rel=1e-9)
    R2, R3, M = _resultants(r)
    assert (R2, R3) == pytest.approx((0, 0), abs=1e-9)
    assert M == pytest.approx(500.0, rel=1e-9)
    assert np.abs(_node_balance(r, len(nodes))).max() < 1e-9


def test_load_off_shear_centre_adds_torque():
    b, d = 0.08, 0.12
    nodes = [(0, 0), (b, 0), (b, d), (0, d)]
    walls = [(0, 1, 0.004), (1, 2, 0.002), (2, 3, 0.004), (3, 0, 0.002)]
    r = shear_flow(nodes, walls, Q3=1000.0, load_point=(b, d / 2))
    assert r.torque_SC == pytest.approx(1000.0 * b / 2)
    assert _resultants(r)[2] == pytest.approx(1000.0 * b, rel=1e-6)


def test_z_section():
    b, d, h = 0.05, 0.12, 0.003
    r = shear_flow([(-b, 0), (0, 0), (0, d), (b, d)], [(0, 1, h), (1, 2, h), (2, 3, h)], Q2=200.0, Q3=1000.0)
    assert r.J23 != pytest.approx(0)
    assert _resultants(r)[:2] == pytest.approx((200.0, 1000.0), rel=1e-6)
    assert (r.x2_SC, r.x3_SC) == pytest.approx((0, d / 2), abs=1e-9)


def test_open_section_torque_is_saint_venant():
    b, d, h = 0.05, 0.1, 0.002
    r = shear_flow([(b, 0), (0, 0), (0, d), (b, d)], [(0, 1, h), (1, 2, h), (2, 3, h)], Q3=0.0, Mt=2.0)
    J_T = (2 * b + d) * h**3 / 3
    assert r.J_T == pytest.approx(J_T)
    assert r.tau_torsion_open == pytest.approx(2.0 * h / J_T)
    assert r.t_max == pytest.approx(0, abs=1e-12) and r.note


@pytest.mark.parametrize("nodes, walls", [
    ([(0, 0)], [(0, 0, 0.001)]),                                    # < 2 nodes
    ([(0, 0), (1, 0)], [(0, 2, 0.001)]),                            # bad index
    ([(0, 0), (0, 0), (1, 1)], [(0, 1, 0.001), (1, 2, 0.001)]),     # zero length
    ([(0, 0), (1, 0), (1, 1)], [(0, 1, 0.001), (1, 0, 0.001), (1, 2, 0.001)]),  # duplicate
    ([(0, 0), (1, 0), (1, 1), (2, 2)], [(0, 1, 0.001), (2, 3, 0.001)]),  # disconnected
    ([(0, 0), (1, 0), (2, 0)], [(0, 1, 0.001), (1, 2, 0.001)]),     # singular (straight line)
    ([(0, 0), (1, 0), (1, 1)], [(0, 1, 0.0), (1, 2, 0.001)]),       # h <= 0
    ([(0, 0), (1, 0), (1, 1)], [(0, 1, 0.001, -1.0), (1, 2, 0.001)]),  # G <= 0
])
def test_validation_errors(nodes, walls):
    with pytest.raises(ValueError):
        shear_flow(nodes, walls)
