"""Section properties against hand formulas."""
import math

import pytest

from engtoolkit.structural import (
    Beam, CBeam, Circle, HollowCircle, IBeam, LBeam, Rectangle, RectangularTube, TBeam, ZBeam, I_beam, beam,
)


def test_rectangle_properties():
    s = Rectangle(width=0.1, height=0.2)
    assert s.area == pytest.approx(0.02)
    assert s.Iyy == pytest.approx(0.1 * 0.2**3 / 12)
    assert s.Izz == pytest.approx(0.2 * 0.1**3 / 12)
    assert s.Iy == s.Iyy and s.Iz == s.Izz  # notebook aliases
    assert s.W_el_y == pytest.approx(0.1 * 0.2**2 / 6)


def test_rectangle_torsion_constant_square():
    # Square section: J ≈ 0.1406 a^4 (Roark)
    a = 0.05
    assert Rectangle(a, a).J_torsion == pytest.approx(0.1406 * a**4, rel=5e-3)


def test_circle_and_hollow_circle():
    r = 0.03
    assert Circle(r).Iyy == pytest.approx(math.pi * r**4 / 4)
    assert Circle(r).J_torsion == pytest.approx(math.pi * r**4 / 2)
    ro, ri = 0.05, 0.04
    h = HollowCircle(ro, ri)
    assert h.Iyy == pytest.approx(math.pi / 4 * (ro**4 - ri**4))
    assert h.W_torsion == pytest.approx(h.J_torsion / ro)


def test_i_beam_strong_axis_by_hand():
    # Flange 200 x 20, web 300 x 10 (mm)
    s = IBeam(0.2, 0.02, 0.3, 0.01)
    flanges = 2 * (0.2 * 0.02**3 / 12 + 0.2 * 0.02 * (0.15 + 0.01)**2)
    web = 0.01 * 0.3**3 / 12
    assert s.Iyy == pytest.approx(flanges + web)
    assert s.area == pytest.approx(2 * 0.2 * 0.02 + 0.3 * 0.01)
    assert s.height == pytest.approx(0.34)


def test_ipe_profile_close_to_published_values():
    # EN 10365 IPE 200: A = 28.5 cm², Iy = 1943 cm⁴ including root fillets, which we ignore (~5 %)
    s = IBeam.from_profile("IPE 200")
    assert s.area == pytest.approx(28.5e-4, rel=0.06)
    assert s.Iyy == pytest.approx(1943e-8, rel=0.06)
    assert s.Iyy < 1943e-8  # fillets ignored, so slightly low


def test_t_beam_centroid_and_parallel_axis():
    s = TBeam(0.1, 0.01, 0.1, 0.01)  # flange 100 x 10 on a 100 x 10 web
    assert s.CoG_y == pytest.approx((0.001 * 0.105 + 0.001 * 0.05) / 0.002)
    y = s.CoG_y
    expected = (0.1 * 0.01**3 / 12 + 0.001 * (0.105 - y)**2
                + 0.01 * 0.1**3 / 12 + 0.001 * (0.05 - y)**2)
    assert s.Iyy == pytest.approx(expected)
    assert s.c_top + s.c_bottom == pytest.approx(s.height)


def test_channel_area_includes_both_flanges():
    s = CBeam(0.05, 0.005, 0.1, 0.004)
    assert s.area == pytest.approx(2 * 0.05 * 0.005 + 0.1 * 0.004)
    assert s.CoS_z < 0  # shear centre lies behind the web


def test_z_section_has_product_of_inertia():
    assert ZBeam(0.05, 0.005, 0.1, 0.004).Iyz != 0


def test_equal_angle_centroid():
    # 100 x 100 x 10 angle: centroid 28.7 mm from the back of each leg
    s = LBeam(0.1, 0.01)
    assert s.CoG_y == pytest.approx(0.02868, abs=1e-4)


def test_rectangular_tube_bredt():
    s = RectangularTube(0.03, 0.05, 0.003)
    Am = 0.027 * 0.047
    assert s.A_enclosed == pytest.approx(Am)
    assert s.J_torsion == pytest.approx(4 * Am**2 * 0.003 / (2 * (0.027 + 0.047)))


@pytest.mark.parametrize("section", [
    Rectangle(0.1, 0.2), Circle(0.05), HollowCircle(0.05, 0.04), RectangularTube(0.1, 0.15, 0.005),
    IBeam(0.1, 0.008, 0.2, 0.005), TBeam(0.1, 0.01, 0.1, 0.008), CBeam(0.05, 0.006, 0.1, 0.005),
    ZBeam(0.05, 0.006, 0.1, 0.005), LBeam(0.08, 0.008),
])
def test_outline_area_matches_section_area(section):
    """Shoelace area of the outline (minus holes) equals the section area."""
    def poly_area(pts):
        return 0.5 * abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1])))
    shape = section.outline()
    area = poly_area(shape["outer"]) - sum(poly_area(h) for h in shape["holes"])
    assert area == pytest.approx(section.area, rel=2e-3)  # circles are 72-gons


def test_beam_mass_si_and_old_names():
    b = Beam("Steel", 2.0, IBeam(0.2, 0.02, 0.3, 0.01))
    assert b.get_mass() == pytest.approx(0.011 * 2.0 * 7850)
    assert beam is Beam and I_beam is IBeam
