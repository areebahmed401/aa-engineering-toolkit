"""
Validation tests for the ASME VIII-1 tools.

Worked examples are hand calculations from the code equations (US customary inputs converted to SI,
as in the Megyesy / Moss examples), so every expected number can be reproduced on a calculator.
"""
import math

import pytest

from engtoolkit import run
from engtoolkit.asme.div1 import (
    Nozzle, cylindrical_shell, external_pressure_cylinder, factor_A, flat_head, formed_head, next_plate,
    nozzle_reinforcement, spherical_shell, vessel_design,
)

PSI = 6894.757293168
IN = 0.0254

# Example: P = 100 psi, D = 96 in (R = 48 in), S = 20 000 psi, E = 0.85, CA = 0.125 in
P, D, S, E, CA = 100 * PSI, 96 * IN, 20000 * PSI, 0.85, 0.125 * IN


def test_tool_cylindrical_shell():
    # UG-27(c)(1): t = PR/(SE − 0.6P) = 100·48.125/(17 000 − 60) = 0.28409 in; + CA = 0.40909 in
    r = run("asme.cylindrical_shell", P=P, D_inside=D, S=S, E=E, corrosion=CA, t_nominal=0.4375 * IN)
    assert r.t_circumferential / IN == pytest.approx(0.28409, rel=1e-4)
    assert r.t_required / IN == pytest.approx(0.40909, rel=1e-4)
    # UG-27(c)(2): t = PR/(2SE + 0.4P) = 4812.5/34 040 = 0.14138 in
    assert r.t_longitudinal / IN == pytest.approx(0.14138, rel=1e-4)
    assert r.governing == "circumferential stress" and r.clause == "UG-27(c)(1)"
    # MAWP at 7/16 in nominal: t = 0.3125 in, P = SEt/(R + 0.6t) = 5312.5/48.3125 = 109.96 psi
    assert r.mawp / PSI == pytest.approx(109.96, rel=1e-4)
    assert r.status == "PASS"


def test_cylinder_thick_wall_appendix_1_2():
    # at P = 0.385SE the thin formula (0.385R/0.769 = 0.50065R) and Appendix 1-2 (0.50068R) agree
    R = 0.5
    at_limit = cylindrical_shell(0.385 * 100e6, 2 * R, 100e6)
    assert at_limit.t_circumferential / R == pytest.approx(0.385 / 0.769, rel=1e-4)
    thick = cylindrical_shell(0.5 * 100e6, 2 * R, 100e6)
    assert thick.clause == "Appendix 1-2(a)(1)"
    assert thick.t_circumferential == pytest.approx(R * (math.sqrt(1.5 / 0.5) - 1), rel=1e-9)
    # MAWP inverts the thickness formula
    exact = cylindrical_shell(0.5 * 100e6, 2 * R, 100e6, t_nominal=thick.t_circumferential)
    assert exact.mawp == pytest.approx(0.5 * 100e6, rel=1e-9)


def test_ug16_minimum_and_plate_rounding():
    r = cylindrical_shell(10e3, 0.3, 138e6)
    assert r.t_pressure < 1.5e-3 and r.t_required == pytest.approx(1.5e-3)
    assert next_plate(8.17e-3) == pytest.approx(10e-3) and next_plate(6e-3) == pytest.approx(6e-3)


def test_tool_spherical_shell():
    # UG-27(d): t = PR/(2SE − 0.2P) = 4812.5/(34 000 − 20) = 0.14163 in
    r = run("asme.spherical_shell", P=P, D_inside=D, S=S, E=E, corrosion=CA)
    assert r.t_pressure / IN == pytest.approx(0.14163, rel=1e-4)
    assert r.clause == "UG-27(d)"
    thick = spherical_shell(0.8 * 100e6, 1.0, 100e6)
    Y = 2 * (1.8) / (2 - 0.8)
    assert thick.clause == "Appendix 1-3" and thick.t_pressure == pytest.approx(0.5 * (Y ** (1 / 3) - 1))


def test_tool_formed_head():
    # UG-32(c) 2:1 ellipsoidal, D = 96.25 in corroded: t = PD/(2SE − 0.2P) = 9625/33 980 = 0.28325 in
    e = run("asme.formed_head", kind="ellipsoidal_2_1", P=P, D_inside=D, S=S, E=E, corrosion=CA)
    assert e.t_pressure / IN == pytest.approx(0.28325, rel=1e-4)
    # general ellipsoidal with D/2h = 2 has K = 1 and reproduces the 2:1 formula
    g = formed_head(P, D, S, "ellipsoidal", E, CA, ratio=2.0)
    assert g.factor == pytest.approx(1.0) and g.t_pressure == pytest.approx(e.t_pressure)
    # UG-32(d) torispherical, L = 96.125 in corroded: t = 0.885PL/(SE − 0.1P) = 8507.06/16 990 = 0.50071 in
    t = run("asme.formed_head", kind="torispherical", P=P, D_inside=D, S=S, E=E, corrosion=CA)
    assert t.t_pressure / IN == pytest.approx(0.50071, rel=1e-4)
    assert t.clause.startswith("UG-32(d)")
    # Appendix 1-4(d) with M = (3 + √(1/0.06))/4 = 1.7706 agrees with the 0.885 form within 0.1 %
    six = formed_head(P, D, S, "torispherical", E)
    m = formed_head(P, D, S, "torispherical", E, knuckle_radius=0.06 * D * (1 + 1e-6))
    assert m.clause == "Appendix 1-4(d)" and m.t_pressure == pytest.approx(six.t_pressure, rel=1e-3)
    # UG-32(f) hemispherical equals the sphere: 0.14163 in
    h = run("asme.formed_head", kind="hemispherical", P=P, D_inside=D, S=S, E=E, corrosion=CA)
    assert h.t_pressure / IN == pytest.approx(0.14163, rel=1e-4)
    assert h.depth == pytest.approx(D / 2)


def test_tool_flat_head():
    # UG-34 eq. (1): t = d√(CP/SE) = 24·√(0.33·100/17 500) = 1.04221 in
    r = run("asme.flat_head", P=P, d=24 * IN, S=17500 * PSI, C=0.33, corrosion=0)
    assert r.t_pressure / IN == pytest.approx(1.04221, rel=1e-4)
    assert r.clause == "UG-34 eq. (1)"
    # MAWP inverts: SE(t/d)²/C at t = t_pressure gives P
    exact = flat_head(P, 24 * IN, 17500 * PSI, 0.33, t_nominal=r.t_pressure)
    assert exact.mawp == pytest.approx(P, rel=1e-9)
    bolted = flat_head(P, 24 * IN, 17500 * PSI, 0.3, W=200e3, h_G=0.03)
    assert bolted.clause == "UG-34 eq. (2)" and bolted.t_pressure > flat_head(P, 24 * IN, 17500 * PSI, 0.3).t_pressure


def test_tool_nozzle_reinforcement():
    # Hand calculation: P = 1 MPa, cylinder D = 1.2 m, t = 12 mm, S = 138 MPa, nozzle d = 150 mm, tn = 8 mm,
    # no corrosion, no pad, no welds.
    # tr = PR/(S − 0.6P) = 0.6/137.4 = 4.36681 mm; A = d·tr = 655.02 mm²
    # A1 = max(d, 2(t + tn))·(t − tr) = 150·7.63319 = 1144.98 mm²
    # trn = 75/137.4 = 0.54585 mm; A2 = min(5(tn − trn)t, 5(tn − trn)tn) = 5·7.45415·8 = 298.17 mm²
    r = run("asme.nozzle_reinforcement", P=1e6, host="cylinder", D_host=1.2, t_host=12e-3, S_host=138e6,
            d_nozzle=0.15, t_nozzle=8e-3, corrosion=0, pad_diameter=0, pad_thickness=0, weld_leg_nozzle=0,
            weld_leg_pad=0)
    assert r.tr * 1e3 == pytest.approx(4.36681, rel=1e-5)
    assert r.A_required * 1e6 == pytest.approx(655.02, rel=1e-4)
    assert r.A1 * 1e6 == pytest.approx(1144.98, rel=1e-4)
    assert r.A2 * 1e6 == pytest.approx(298.17, rel=1e-4)
    assert r.A_available * 1e6 == pytest.approx(1443.15, rel=1e-4)
    assert r.status == "PASS" and not r.small_opening_exempt
    # with a 300 mm × 10 mm pad: A5 = (Dp − d − 2tn)·te = (300 − 150 − 16)·10 = 1340 mm²
    p = nozzle_reinforcement(1e6, "cylinder", 1.2, 12e-3, 138e6, 0.15, 8e-3, pad_diameter=0.3, pad_thickness=10e-3)
    assert p.A5 * 1e6 == pytest.approx(1340, rel=1e-6)
    # a thin shell that only just meets the pressure fails without a pad
    thin = nozzle_reinforcement(1e6, "cylinder", 1.2, 4.4e-3, 138e6, 0.15, 5e-3)
    assert thin.status == "FAIL"
    # small openings are exempt by UG-36(c)(3)
    assert nozzle_reinforcement(1e6, "cylinder", 1.2, 4.4e-3, 138e6, 0.05, 5e-3).status == "PASS"


def test_nozzle_host_required_thickness_ug37a():
    from engtoolkit.asme.div1 import required_host_thickness
    # 2:1 ellipsoidal head: equivalent sphere radius 0.9D
    assert required_host_thickness(1e6, "ellipsoidal_2_1", 1.2, 138e6) == pytest.approx(1e6 * 1.08 / (276e6 - 0.2e6))
    # torispherical: sphere of crown radius L
    assert required_host_thickness(1e6, "torispherical", 1.2, 138e6) == pytest.approx(1.2e6 / (276e6 - 0.2e6))


def test_tool_external_pressure():
    # long cylinder (L/Do ≥ 50): A = (t/Do)²/(1 − ν²) = 1.0989e-4 for Do/t = 100 (Fig. G long line ≈ 1.1/(Do/t)²)
    assert factor_A(60.0, 1.0, 0.01) == pytest.approx(1e-4 / 0.91, rel=1e-9)
    r = run("asme.external_pressure", P_external=50e3, Do=1.0, L=60.0, t_nominal=0.01, corrosion=0,
            E_modulus=200e9)
    # elastic: Pa = 2AE/(3·Do/t) = 2·1.0989e-4·200e9/300 = 146.52 kPa
    assert r.P_allowable == pytest.approx(2 * (1e-4 / 0.91) * 200e9 / 300, rel=1e-9)
    assert r.status == "PASS"
    # with factor B from the material chart: Pa = 4B/(3·Do/t)
    b = external_pressure_cylinder(50e3, 1.0, 3.0, 0.01, 200e9, B=60e6)
    assert b.P_allowable == pytest.approx(4 * 60e6 / 300) and b.method.endswith("(factor B)")
    # shorter cylinders buckle at higher pressure
    assert factor_A(1.0, 1.0, 0.01) > factor_A(10.0, 1.0, 0.01)
    # Do/t < 10: UG-28(c)(2) Pa = min((2.167/(Do/t) − 0.0833)B, 2S/(Do/t)·(1 − 1/(Do/t)))
    thick = external_pressure_cylinder(1e6, 0.5, 2.0, 0.06, 200e9, B=100e6, S=138e6)
    Dt = 0.5 / 0.06
    assert thick.P_allowable == pytest.approx(min((2.167 / Dt - 0.0833) * 100e6, 2 * 138e6 / Dt * (1 - 1 / Dt)))
    # required thickness (elastic) gives exactly the external pressure
    need = external_pressure_cylinder(101325, 1.22, 3.4, 0.01, 200e9)
    check = external_pressure_cylinder(101325, 1.22, 3.4, need.t_required_elastic, 200e9)
    assert check.P_allowable == pytest.approx(101325, rel=1e-6)


def test_tool_hydrotest():
    # UG-99(b): 1.3 × 1.0 MPa × (138/118) = 1.52034 MPa
    r = run("asme.hydrotest", mawp=1e6, S_test=138e6, S_design=118e6)
    assert r.test_pressure == pytest.approx(1.3e6 * 138 / 118)
    assert r.stress_ratio == pytest.approx(138 / 118)


def test_tool_vessel_design():
    r = run("asme.vessel_design")
    assert r.status == "PASS"
    shell = cylindrical_shell(1e6, 1.2, 138e6, 0.85, 3e-3)
    head = formed_head(1e6, 1.2, 138e6, "ellipsoidal_2_1", 1.0, 3e-3)
    assert r.shell_t_nominal == shell.t_nominal and r.head_t_nominal == head.t_nominal
    assert r.mawp == pytest.approx(min(shell.mawp, head.mawp))
    assert r.hydro_test_pressure == pytest.approx(1.3 * r.mawp)
    assert r.nozzles_passing == "1/1"
    assert "Verify against the current code edition" in r.to_markdown()

    # undersized shell plate fails, and full vacuum adds a UG-28 check
    bad = run("asme.vessel_design", {"shell": {"t_nominal": 6e-3}, "conditions": {"P": 1e6, "P_external": 101325}})
    assert bad.status == "FAIL"
    assert any(c["item"] == "Shell thickness" and c["status"] == "FAIL" for c in bad.checks)
    assert any(c["clause"] == "UG-28(c)" for c in bad.checks)

    sphere = vessel_design(1e6, 2.0, 138e6, shell_kind="sphere",
                           nozzles=[Nozzle(pad_diameter=0.3, pad_thickness=10e-3, weld_leg=6e-3)])
    assert sphere.head is None and math.isnan(sphere.head_t_nominal) and sphere.status == "PASS"
    flat = vessel_design(0.3e6, 0.6, 138e6, head_kind="flat", nozzles=[Nozzle(location="head")])
    assert flat.head.kind == "flat" and any("UG-39" in n for n in flat.notes)
