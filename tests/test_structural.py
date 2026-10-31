"""Structural library checked against closed-form textbook results."""
import math

import numpy as np
import pytest

from utils.Appendix.materials import get_material
from utils.Appendix.structural import (
    Rectangle, Circle, Hollow_Circle, Rectangular_Tube, I_beam, T_beam, C_beam, L_beam,
    beam, PointLoad, DistributedLoad, MomentLoad, Fixed, Pinned, Roller, Free,
    FEMSolver, DeterminateSolver, Torsion, static_determinacy,
)

STEEL = get_material("Steel")
L = 2.0
P = 10e3
W = 5e3
SECTION = Rectangle(width=0.1, height=0.2)
EI = STEEL.E * SECTION.Iyy


def make_beam(left, right, *loads, shape=SECTION, length=L):
    b = beam(STEEL, length, shape)
    b.set_end_conditions(left, right)
    for load in loads:
        b.add_load(load)
    return b


def fem(b, n_elem=40, theory="EB"):
    solver = FEMSolver(b, n_elem, theory=theory)
    solver.solve()
    return solver


# ---------------- cross-sections ----------------

def test_rectangle_properties():
    s = Rectangle(width=0.1, height=0.2)
    assert s.area == pytest.approx(0.02)
    assert s.Iyy == pytest.approx(0.1 * 0.2**3 / 12)
    assert s.Izz == pytest.approx(0.2 * 0.1**3 / 12)
    assert s.Iy == s.Iyy and s.Iz == s.Izz  # notebook aliases


def test_rectangle_torsion_constant_square():
    # Square section: J ≈ 0.1406 a^4 (Roark)
    a = 0.05
    assert Rectangle(a, a).J_torsion == pytest.approx(0.1406 * a**4, rel=5e-3)


def test_circle_and_hollow_circle():
    r = 0.03
    assert Circle(r).Iyy == pytest.approx(math.pi * r**4 / 4)
    assert Circle(r).J_torsion == pytest.approx(math.pi * r**4 / 2)
    ro, ri = 0.05, 0.04
    h = Hollow_Circle(ro, ri)
    assert h.Iyy == pytest.approx(math.pi / 4 * (ro**4 - ri**4))
    assert h.W_torsion == pytest.approx(h.J_torsion / ro)


def test_i_beam_strong_axis_by_hand():
    # Flange 200 x 20, web 300 x 10 (mm)
    s = I_beam(0.2, 0.02, 0.3, 0.01)
    flanges = 2 * (0.2 * 0.02**3 / 12 + 0.2 * 0.02 * (0.15 + 0.01)**2)
    web = 0.01 * 0.3**3 / 12
    assert s.Iyy == pytest.approx(flanges + web)
    assert s.area == pytest.approx(2 * 0.2 * 0.02 + 0.3 * 0.01)


def test_t_beam_centroid_and_parallel_axis():
    s = T_beam(0.1, 0.01, 0.1, 0.01)  # flange 100 x 10 on a 100 x 10 web
    assert s.CoG_y == pytest.approx((0.001 * 0.105 + 0.001 * 0.05) / 0.002)
    y = s.CoG_y
    expected = (0.1 * 0.01**3 / 12 + 0.001 * (0.105 - y)**2
                + 0.01 * 0.1**3 / 12 + 0.001 * (0.05 - y)**2)
    assert s.Iyy == pytest.approx(expected)


def test_channel_area_includes_both_flanges():
    s = C_beam(0.05, 0.005, 0.1, 0.004)
    assert s.area == pytest.approx(2 * 0.05 * 0.005 + 0.1 * 0.004)
    assert s.CoS_z < 0  # shear centre lies behind the web


def test_equal_angle_centroid():
    # 100 x 100 x 10 angle: centroid 28.7 mm from the back of each leg
    s = L_beam(0.1, 0.01)
    assert s.CoG_y == pytest.approx(0.02868, abs=1e-4)


def test_rectangular_tube_bredt():
    s = Rectangular_Tube(0.03, 0.05, 0.003)
    Am = 0.027 * 0.047
    assert s.A_enclosed == pytest.approx(Am)
    assert s.J_torsion == pytest.approx(4 * Am**2 * 0.003 / (2 * (0.027 + 0.047)))


def test_beam_mass_si():
    b = beam(STEEL, 2.0, I_beam(0.2, 0.02, 0.3, 0.01))
    assert b.get_mass() == pytest.approx(0.011 * 2.0 * 7850)


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
    assert static_determinacy(b) > 0
    s = fem(b)
    _, _, M = s.bending_moment_shear()
    assert M[0] == pytest.approx(-W * L**2 / 12, rel=1e-6)
    assert M[len(M) // 2] == pytest.approx(W * L**2 / 24, rel=1e-6)
    assert s.deflection()[1][s.n_elem // 2] == pytest.approx(-W * L**4 / (384 * EI), rel=1e-6)


def test_point_load_between_nodes():
    # Load at x = 0.73 m does not sit on a node of the 10-element mesh
    a = 0.73
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
    EI_deep = STEEL.E * deep.Iyy
    expected = -(P * length**3 / (3 * EI_deep) + P * length / (5 / 6 * STEEL.G * deep.area))
    assert tb == pytest.approx(expected, rel=1e-6)


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


# ---------------- Torsion ----------------

def test_warping_torsion_closed_form():
    alu = get_material("Aluminum")
    b = beam(alu, 1.0, I_beam(0.3, 0.01, 0.4, 0.01))
    t = Torsion(b, TorsionalMoment=200, position=1.0)
    a = t.alpha
    saint_venant = 200 * 1.0 / (alu.G * b.shape.J_torsion)
    assert t.theta() == pytest.approx(saint_venant * (1 - math.tanh(a) / a))
    assert Torsion(b, 200, 0.0).theta() == pytest.approx(0.0, abs=1e-15)


def test_warping_torsion_tends_to_saint_venant_for_long_beam():
    alu = get_material("Aluminum")
    b = beam(alu, 200.0, I_beam(0.3, 0.01, 0.4, 0.01))
    t = Torsion(b, TorsionalMoment=200, position=200.0)
    saint_venant = 200 * 200.0 / (alu.G * b.shape.J_torsion)
    assert t.alpha > 50
    assert t.theta() == pytest.approx(saint_venant, rel=0.02)
