"""Torsion: free warping (Saint-Venant) section constants and the restrained-warping solver (formulary §3)."""
import math

import numpy as np
import pytest

from engtoolkit.core.registry import run
from engtoolkit.materials import get_material
from engtoolkit.structural.sections import (
    Beam, CBeam, Circle, Ellipse, HollowCircle, IBeam, LBeam, Rectangle, RectangularTube, TBeam, ZBeam,
    rect_torsion_eta,
)
from engtoolkit.structural.thin_walled import sectorial
from engtoolkit.structural.torsion import Torsion, solve_torsion

GJ = 80e9 * 1e-8


# ---------------- free warping: section constants ----------------

@pytest.mark.parametrize("ratio, eta1, eta2", [(1, 0.4217, 0.6245), (2, 0.6860, 0.7376), (4, 0.8424, 0.8450),
                                               (10, 0.9370, 0.9370)])
def test_rectangle_eta_matches_formulary_table(ratio, eta1, eta2):
    e1, e2 = rect_torsion_eta(ratio)
    assert e1 == pytest.approx(eta1, abs=1.5e-3)
    assert e2 == pytest.approx(eta2, abs=1.5e-3)


def test_rectangle_eta_tends_to_one_and_uses_short_side():
    e1, e2 = rect_torsion_eta(1e4)
    assert e1 == pytest.approx(1, abs=1e-4) and e2 == pytest.approx(1, abs=1e-4)
    B, H = 0.02, 0.08
    r = Rectangle(H, B)  # orientation does not matter
    assert r.J_torsion == pytest.approx(rect_torsion_eta(4)[0] * B**3 * H / 3)
    assert r.W_torsion == pytest.approx(rect_torsion_eta(4)[1] * B**2 * H / 3)


def test_ellipse_constants_and_circle_limit():
    a, b = 0.05, 0.03
    e = Ellipse(a, b)
    assert e.J_torsion == pytest.approx(math.pi * a**3 * b**3 / (a**2 + b**2))
    assert e.W_torsion == pytest.approx(math.pi * a * b**2 / 2)
    assert Ellipse(b, a).W_torsion == pytest.approx(e.W_torsion)  # smaller semi-axis is b
    assert e.area == pytest.approx(math.pi * a * b)
    c, r = Ellipse(0.04, 0.04), Circle(0.04)
    assert c.J_torsion == pytest.approx(r.J_torsion) and c.W_torsion == pytest.approx(r.W_torsion)


def test_thick_rectangular_tube_tends_to_bredt():
    for t, tol in ((1e-4, 2e-3), (1e-5, 2e-4)):
        s = RectangularTube(0.1, 0.15, t)
        Bm, Hm = 0.1 - t, 0.15 - t
        assert s.J_torsion == pytest.approx(4 * (Bm * Hm)**2 * t / (2 * (Bm + Hm)), rel=tol)
        assert s.W_torsion == pytest.approx(2 * Bm * Hm * t, rel=tol)
    thick = RectangularTube(0.1, 0.15, 0.02).thick_wall_torsion()
    assert thick["J"] > thick["J_TB"] and 0 < thick["share_B"] < 1


def test_hollow_circle_thin_wall_matches_bredt():
    R, h = 0.05, 1e-4
    s = HollowCircle(R, R - h)
    rm = R - h / 2
    assert s.J_torsion == pytest.approx(4 * (math.pi * rm**2)**2 * h / (2 * math.pi * rm), rel=1e-6)
    assert s.J_torsion == pytest.approx(math.pi * (R**4 - (R - h)**4) / 2)  # exact thick formula kept


def test_open_shape_eta3():
    assert IBeam(0.1, 0.01, 0.2, 0.006).J_torsion == pytest.approx(1.30 / 3 * (2 * 0.1 * 0.01**3 + 0.2 * 0.006**3))
    for cls in (CBeam, ZBeam):
        assert cls(0.1, 0.01, 0.2, 0.006).J_torsion == pytest.approx(1.12 / 3 * (2 * 0.1 * 0.01**3 + 0.2 * 0.006**3))
    assert TBeam(0.1, 0.01, 0.2, 0.006).J_torsion == pytest.approx(1.12 / 3 * (0.1 * 0.01**3 + 0.2 * 0.006**3))
    assert LBeam(0.08, 0.008).J_torsion == pytest.approx(0.99 / 3 * (2 * 0.08 - 0.008) * 0.008**3)


# ---------------- sectorial coordinate / C_T ----------------

@pytest.mark.parametrize("section", [IBeam(0.1, 0.008, 0.2, 0.005), CBeam(0.05, 0.006, 0.1, 0.005),
                                     ZBeam(0.05, 0.006, 0.1, 0.005), IBeam.from_profile("IPE 200")])
def test_sectorial_C_T_matches_formulary(section):
    """I: C_T = a² J_F/2; C: a²b²A_F(1/6 − A_F/(8A_F + 4/3 A_S)); Z: a²b²A_F(1/6 − A_F/(8A_F + 4A_S))."""
    r = sectorial(*section.midline())
    assert r.C_T == pytest.approx(section.C_torsion, rel=1e-10)
    assert section.omega_max == pytest.approx(r.omega_max) and r.omega_max > 0


def test_sectorial_i_beam_omega_max():
    s = IBeam(0.1, 0.008, 0.2, 0.005)
    assert s.omega_max == pytest.approx((0.2 + 0.008) / 2 * 0.1 / 2)  # ω = (h/2)(b/2) at the flange tips


@pytest.mark.parametrize("section", [TBeam(0.1, 0.01, 0.1, 0.008), LBeam(0.08, 0.008)])
def test_sectorial_T_and_L_have_no_warping(section):
    assert sectorial(*section.midline()).C_T == pytest.approx(0.0, abs=1e-20)


def test_sectorial_is_principal_and_rejects_closed_sections():
    nodes, walls = ZBeam(0.05, 0.006, 0.1, 0.005).midline()
    r = sectorial(nodes, walls)
    P = np.array(nodes)
    om = np.array(r.omega_nodes)
    for c in (None, 0, 1):
        total = 0.0
        for i, j, h in walls:
            l = float(np.hypot(*(P[j] - P[i])))
            if c is None:
                total += h * l * (om[i] + om[j]) / 2
            else:
                total += h * l * (2 * om[i] * P[i, c] + om[i] * P[j, c] + om[j] * P[i, c] + 2 * om[j] * P[j, c]) / 6
        assert total == pytest.approx(0.0, abs=1e-12)
    with pytest.raises(ValueError):
        sectorial([(0, 0), (1, 0), (1, 1), (0, 1)], [(0, 1, 0.01), (1, 2, 0.01), (2, 3, 0.01), (3, 0, 0.01)])


# ---------------- restrained warping solver ----------------

def _cantilever():
    alu = get_material("Aluminum")
    b = Beam(alu, 1.0, IBeam(0.3, 0.01, 0.4, 0.01))
    return b, alu.G * b.shape.J_torsion, alu.E * b.shape.C_torsion


def test_fixed_free_matches_formulary_closed_form():
    b, gj, ec = _cantilever()
    sol = solve_torsion(1.0, gj, ec, "fixed", "free", [(1.0, 200.0)])
    for xi in (0.0, 0.1, 0.4, 0.75, 1.0):
        assert sol.at(xi)["theta"] == pytest.approx(Torsion(b, 200, xi).theta(), rel=1e-10, abs=1e-15)
    assert sol.alpha == pytest.approx(Torsion(b, 200, 1.0).alpha)
    assert np.allclose(sol.T, 200.0)


@pytest.mark.parametrize("alpha", [1e-3, 0.3, 5.0, 80.0, 1e3])
def test_fixed_free_all_alpha(alpha):
    """θ(L) = T L/(G J_T) (1 − tanh α/α), no overflow for large α."""
    ec = GJ / alpha**2
    sol = solve_torsion(1.0, GJ, ec, "fixed", "free", [(1.0, 100.0)])
    assert sol.at(1.0)["theta"] == pytest.approx(100 / GJ * (1 - math.tanh(alpha) / alpha), rel=1e-6)
    assert np.all(np.isfinite(sol.M_b)) and np.allclose(sol.M_sv + sol.M_b, 100.0)


def test_large_alpha_approaches_saint_venant():
    sol = solve_torsion(1.0, GJ, GJ / 1e3**2, "fixed", "free", [(1.0, 100.0)])
    assert sol.at(1.0)["theta"] == pytest.approx(100 / GJ, rel=2e-3)


@pytest.mark.parametrize("alpha", [0.5, 3.0, 30.0, 300.0])
def test_fork_fork_and_fixed_fixed_midspan_torque(alpha):
    """
    Point torque T0 at mid-span; by symmetry each half carries T0/2 with ϑ'(L/2) = 0 (Kollbrunner & Basler,
    Torsion in Structures, warping torsion tables):
      fork-fork:   ϑ(L/2) = T0 L/(4 G J_T) [1 − (2/α) tanh(α/2)]
      fixed-fixed: ϑ(L/2) = T0 L/(4 G J_T) [1 − (4/α) tanh(α/4)]
    """
    ec, T0, L = GJ * 2.0**2 / alpha**2, 150.0, 2.0
    s = solve_torsion(L, GJ, ec, "fork", "fork", [(L / 2, T0)])
    assert s.at(L / 2)["theta"] == pytest.approx(T0 * L / (4 * GJ) * (1 - 2 / alpha * math.tanh(alpha / 2)), rel=1e-8)
    s = solve_torsion(L, GJ, ec, "fixed", "fixed", [(L / 2, T0)])
    assert s.at(L / 2)["theta"] == pytest.approx(T0 * L / (4 * GJ) * (1 - 4 / alpha * math.tanh(alpha / 4)), rel=1e-8)
    assert s.T[0] == pytest.approx(T0 / 2) and s.T[-1] == pytest.approx(-T0 / 2)


@pytest.mark.parametrize("alpha", [0.5, 4.0, 60.0])
def test_fork_fork_uniform_torque(alpha):
    """
    Uniform m_t on fork-fork: ϑ = (m L²/(G J_T)) [ξ(1 − ξ)/2 + (cosh(α(ξ − ½))/cosh(α/2) − 1)/α²]
    (from E C_T ϑ'''' − G J_T ϑ'' = m_t with ϑ = ϑ'' = 0 at both ends).
    """
    L, m = 3.0, 40.0
    ec = GJ * L**2 / alpha**2
    s = solve_torsion(L, GJ, ec, "fork", "fork", m_t=m)
    for xi in (0.2, 0.5, 0.9):
        exact = m * L**2 / GJ * (xi * (1 - xi) / 2 + (math.cosh(alpha * (xi - 0.5)) / math.cosh(alpha / 2) - 1) / alpha**2)
        assert s.at(xi * L)["theta"] == pytest.approx(exact, rel=1e-8)


@pytest.mark.parametrize("seed", range(6))
def test_equilibrium_random_loads(seed):
    """T(x) = M_SV + M_B satisfies dT/dx = −m_t with jumps −T_k at point torques, and free ends carry their load."""
    rng = np.random.default_rng(seed)
    L = 2.5
    supports = [("fixed", "free"), ("free", "fixed"), ("fork", "fork"), ("fixed", "fixed"), ("fixed", "fork"),
                ("fork", "free")][seed]
    loads = [(float(x), float(T)) for x, T in zip(rng.uniform(0.1, L - 0.1, 3), rng.uniform(-300, 300, 3))]
    loads.append((L, 80.0))
    m = float(rng.uniform(-50, 50))
    for ec in (GJ * L**2 / rng.uniform(0.5, 20) ** 2, 0.0):
        s = solve_torsion(L, GJ, ec, *supports, loads, m_t=m)
        for x, T in zip(s.x, s.T):
            if min(abs(x - xk) for xk, _ in loads) < 1e-9:
                continue
            expected = s.T[0] - m * x - sum(Tk for xk, Tk in loads if xk < x)
            assert T == pytest.approx(expected, abs=1e-6 * 300)
        if supports[1] == "free":
            assert s.T[-1] == pytest.approx(80.0, abs=1e-6)
        if supports[0] == "free":
            assert s.T[0] == pytest.approx(0.0, abs=1e-6)


def test_free_free_raises():
    with pytest.raises(ValueError):
        solve_torsion(1.0, GJ, GJ, "free", "free", [(0.5, 10.0)])
    with pytest.raises(ValueError):
        run("structural.torsion", {"left_support": "free", "right_support": "free"})


# ---------------- tool ----------------

def test_tool_old_payload_gives_formulary_cantilever():
    payload = {"section": {"shape": "i_beam"}, "material": "Steel", "length": 1.0, "torque": 200.0, "position": 0.6}
    r = run("structural.torsion", payload)
    steel = get_material("Steel")
    from engtoolkit.structural.tools import SectionInputs, build_section
    t = Torsion(Beam(steel, 1.0, build_section(SectionInputs(shape="i_beam"))), 200.0, 0.6)
    assert r.twist == pytest.approx(t.theta(), rel=1e-10)
    assert r.alpha == pytest.approx(t.alpha)
    assert r.saint_venant_share == pytest.approx(t.saint_venant_share(0.0), abs=1e-9)
    assert r.max_shear_stress == pytest.approx(200.0 / r.W_T)
    assert len(r.x) >= 101 and r.B_max > 0 and r.sigma_w_max > 0 and r.note == ""
    assert [s["label"] for s in r.steps][:3] == ["J_T (torsion constant)", "W_T (torsional section modulus)",
                                                "C_T (warping constant)"]


def test_tool_free_mode_with_eccentric_force():
    """Free warping cantilever: T = Q2 e3 − Q3 e2 (e = shear centre − load line), ϑ(L) = T L/(G J_T)."""
    r = run("structural.torsion", {"mode": "free", "torque": 0.0, "Q3": 1000.0, "e2": -0.02, "length": 2.0,
                                   "position": 2.0})
    T = -1000.0 * -0.02
    assert r.twist == pytest.approx(T * 2.0 / (get_material("Steel").G * r.J_T))
    assert r.M_b_max == 0 and r.saint_venant_share == 1.0


def test_tool_closed_section_restrained_equals_free():
    p = {"section": {"shape": "rectangular_tube"}, "loads": [{"x": 0.5, "T": 300.0}], "right_support": "fork"}
    r = run("structural.torsion", p)
    rf = run("structural.torsion", {**p, "mode": "free"})
    assert r.twist == pytest.approx(rf.twist) and r.C_T == 0 and "C_T = 0" in r.note
    assert math.isnan(r.alpha)


def test_tool_drawn_sections():
    steel = get_material("Steel")
    # default drawn channel (50 mm flanges, 100 mm web, h = 2 mm) vs the CBeam formulary C_T
    r = run("structural.torsion", {"section_source": "drawn", "mode": "restrained"})
    a, b, h = 0.1, 0.05, 0.002
    Af, As = b * h, a * h
    assert r.C_T == pytest.approx(a**2 * b**2 * Af * (1 / 6 - Af / (8 * Af + 4 / 3 * As)), rel=1e-10)
    assert r.J_T == pytest.approx((2 * b + a) * h**3 / 3) and r.W_T == pytest.approx(r.J_T / h)
    # closed box 100 x 50, h = 2 mm: Bredt J_T = 4A²/∮ds/h, W_T = 2 A h_min
    box = {"section_source": "drawn", "nodes": [{"x2": 0, "x3": 0}, {"x2": 0.1, "x3": 0}, {"x2": 0.1, "x3": 0.05},
                                                {"x2": 0, "x3": 0.05}],
           "walls": [{"i": 0, "j": 1, "h": h}, {"i": 1, "j": 2, "h": h}, {"i": 2, "j": 3, "h": h},
                     {"i": 3, "j": 0, "h": h}], "torque": 100.0}
    r = run("structural.torsion", box)
    A = 0.1 * 0.05
    assert r.J_T == pytest.approx(4 * A**2 * h / 0.3) and r.W_T == pytest.approx(2 * A * h)
    assert r.twist == pytest.approx(100 * 1.0 / (steel.G * r.J_T))


def test_tool_position_beyond_length():
    with pytest.raises(ValueError):
        run("structural.torsion", {"length": 1.0, "position": 2.0})
