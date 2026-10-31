"""FEM and equilibrium solvers checked against closed-form textbook results."""
import math

import numpy as np
import pytest

from engtoolkit.materials import get_material
from engtoolkit.structural import (
    Beam, DeterminateSolver, DistributedLoad, FEMSolver, Fixed, Free, IBeam, MomentLoad, Pinned, PointLoad, Rectangle,
    Roller, Torsion, analyze_beam, static_determinacy,
)

STEEL = get_material("Steel")
L = 2.0
P = 10e3
W = 5e3
SECTION = Rectangle(width=0.1, height=0.2)
EI = STEEL.E * SECTION.Iyy


def make_beam(left, right, *loads, shape=SECTION, length=L):
    b = Beam(STEEL, length, shape)
    b.set_end_conditions(left, right)
    for load in loads:
        b.add_load(load)
    return b


def fem(b, n_elem=40, theory="EB"):
    solver = FEMSolver(b, n_elem, theory=theory)
    solver.solve()
    return solver


# ---------------- FEM vs closed form ----------------

def test_cantilever_tip_load():
    s = fem(make_beam(Fixed(), Free(), PointLoad(P, L)))
    assert s.deflection()[1][-1] == pytest.approx(-P * L**3 / (3 * EI), rel=1e-6)
    R = s.reactions()
    assert R["Ay"] == pytest.approx(P)
    assert R["MA"] == pytest.approx(P * L)
    _, _, M = s.bending_moment_shear()
    assert M[0] == pytest.approx(-P * L)
    assert M[-1] == pytest.approx(0.0, abs=1e-6)


def test_simply_supported_udl():
    s = fem(make_beam(Pinned(), Roller(), DistributedLoad(W)))
    mid = s.n_elem // 2
    assert s.deflection()[1][mid] == pytest.approx(-5 * W * L**4 / (384 * EI), rel=1e-6)
    _, _, M = s.bending_moment_shear()
    assert M.max() == pytest.approx(W * L**2 / 8, rel=1e-6)
    R = s.reactions()
    assert R["Ay"] == pytest.approx(W * L / 2)
    assert R["By"] == pytest.approx(W * L / 2)


def test_fixed_fixed_udl_is_indeterminate_and_matches_theory():
    b = make_beam(Fixed(), Fixed(), DistributedLoad(W))
    assert static_determinacy(b) == 2
    s = fem(b)
    _, _, M = s.bending_moment_shear()
    assert M[0] == pytest.approx(-W * L**2 / 12, rel=1e-6)
    assert M[len(M) // 2] == pytest.approx(W * L**2 / 24, rel=1e-6)
    assert s.deflection()[1][s.n_elem // 2] == pytest.approx(-W * L**4 / (384 * EI), rel=1e-6)


def test_propped_cantilever_reactions():
    # Fixed-pinned, central point load: R_B = 5P/16, R_A = 11P/16, M_A = 3PL/16
    s = fem(make_beam(Fixed(), Pinned(), PointLoad(P, L / 2)))
    R = s.reactions()
    assert R["By"] == pytest.approx(5 * P / 16, rel=1e-6)
    assert R["Ay"] == pytest.approx(11 * P / 16, rel=1e-6)
    assert R["MA"] == pytest.approx(3 * P * L / 16, rel=1e-6)


def test_point_load_between_nodes():
    a = 0.73  # not on a node of the 10-element mesh
    s = fem(make_beam(Pinned(), Roller(), PointLoad(P, a)), n_elem=10)
    R = s.reactions()
    assert R["By"] == pytest.approx(P * a / L)
    assert R["Ay"] == pytest.approx(P * (L - a) / L)


def test_timoshenko_converges_to_eb_for_slender_beam():
    slender = Rectangle(0.01, 0.01)
    b = make_beam(Fixed(), Free(), PointLoad(P, L), shape=slender)
    eb = fem(b, theory="EB").deflection()[1][-1]
    tb = fem(b, theory="TB").deflection()[1][-1]
    assert tb == pytest.approx(eb, rel=1e-3)


def test_timoshenko_adds_shear_deflection():
    deep = Rectangle(0.1, 0.5)
    length = 1.0
    b = make_beam(Fixed(), Free(), PointLoad(P, length), shape=deep, length=length)
    tb = fem(b, theory="TB").deflection()[1][-1]
    expected = -(P * length**3 / (3 * STEEL.E * deep.Iyy) + P * length / (5 / 6 * STEEL.G * deep.area))
    assert tb == pytest.approx(expected, rel=1e-6)


def test_mechanism_is_reported():
    b = make_beam(Free(), Roller(), PointLoad(P, 1.0))
    assert static_determinacy(b) < 0
    with pytest.raises(ValueError):
        analyze_beam(b)


# ---------------- DeterminateSolver ----------------

@pytest.mark.parametrize("left,right", [(Fixed(), Free()), (Free(), Fixed())])
def test_determinate_cantilever_both_sides(left, right):
    x_load = L if isinstance(left, Fixed) else 0.0
    d = DeterminateSolver(make_beam(left, right, PointLoad(P, x_load)))
    _, _, v = d.deflection(4001)
    tip = v[-1] if isinstance(left, Fixed) else v[0]
    assert tip == pytest.approx(-P * L**3 / (3 * EI), rel=1e-3)
    _, _, M = d.shear_moment(401)
    assert np.min(M) == pytest.approx(-P * L, rel=1e-6)


def test_determinate_matches_fem_mixed_loads():
    loads = (DistributedLoad(W, 0.0, 1.0), PointLoad(P, 1.0), MomentLoad(5e3, 1.5))
    d = DeterminateSolver(make_beam(Pinned(), Roller(), *loads))
    s = fem(make_beam(Pinned(), Roller(), *loads), n_elem=80)
    R_d, R_f = d.reactions(), s.reactions()
    assert R_d["Ay"] == pytest.approx(R_f["Ay"], rel=1e-6)
    assert R_d["By"] == pytest.approx(R_f["By"], rel=1e-6)
    x, _, v = d.deflection(4001)
    v_fem = np.interp(x, *s.deflection())
    assert np.max(np.abs(v - v_fem)) < 1e-3 * np.max(np.abs(v_fem))


def test_determinate_rejects_indeterminate():
    with pytest.raises(ValueError):
        DeterminateSolver(make_beam(Fixed(), Pinned(), PointLoad(P, 1.0))).reactions()


# ---------------- analyze_beam picks the method ----------------

def test_analyze_beam_uses_equilibrium_when_determinate():
    r = analyze_beam(make_beam(Pinned(), Roller(), DistributedLoad(W)))
    assert r.degree_of_indeterminacy == 0
    assert r.method.startswith("Equilibrium")
    assert r.max_moment == pytest.approx(W * L**2 / 8, rel=1e-4)
    assert r.max_bending_stress == pytest.approx(W * L**2 / 8 * 0.1 / SECTION.Iyy, rel=1e-4)


def test_analyze_beam_uses_fem_when_indeterminate():
    r = analyze_beam(make_beam(Fixed(), Fixed(), DistributedLoad(W)))
    assert r.degree_of_indeterminacy == 2
    assert r.method.startswith("FEM")
    assert r.max_moment == pytest.approx(W * L**2 / 12, rel=1e-6)


# ---------------- Torsion ----------------

def test_warping_torsion_closed_form():
    alu = get_material("Aluminum")
    b = Beam(alu, 1.0, IBeam(0.3, 0.01, 0.4, 0.01))
    t = Torsion(b, TorsionalMoment=200, position=1.0)
    a = t.alpha
    saint_venant = 200 * 1.0 / (alu.G * b.shape.J_torsion)
    assert t.theta() == pytest.approx(saint_venant * (1 - math.tanh(a) / a))
    assert Torsion(b, 200, 0.0).theta() == pytest.approx(0.0, abs=1e-15)


def test_warping_torsion_tends_to_saint_venant_for_long_beam():
    alu = get_material("Aluminum")
    b = Beam(alu, 200.0, IBeam(0.3, 0.01, 0.4, 0.01))
    t = Torsion(b, TorsionalMoment=200, position=200.0)
    saint_venant = 200 * 200.0 / (alu.G * b.shape.J_torsion)
    assert t.alpha > 50
    assert t.theta() == pytest.approx(saint_venant, rel=0.02)
