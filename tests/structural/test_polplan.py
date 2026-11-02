"""Pole plan (kinematic movability): homogeneous helpers, counting, rule-based construction and exact analysis."""
import math

import numpy as np
import pytest

from engtoolkit import run
from engtoolkit.structural import polplan as pp


# ---------------- model builders ----------------

def beam(xs, joints, supports, y=0.0):
    """Straight beam through the x positions xs (node ids n0, n1, ...); joints: {index: type}."""
    nodes = [{"id": f"n{i}", "x": x, "y": y, "joint": joints.get(i, "rigid")} for i, x in enumerate(xs)]
    members = [{"id": f"m{i}", "a": f"n{i}", "b": f"n{i + 1}"} for i in range(len(xs) - 1)]
    sup = [{"node": f"n{i}", **s} for i, s in supports.items()]
    return {"nodes": nodes, "members": members, "supports": sup}


def pole(res, name):
    return next(p for p in res.poles if p["name"] == name)


def xy(p):
    return (p["x"], p["y"])


# ---------------- homogeneous helpers ----------------

def test_parallel_lines_meet_at_infinity():
    l1 = pp.hline(1, 0, -10)   # x = 10
    l2 = pp.hline(1, 0, 0)     # x = 0
    p = pp.meet(l1, l2)
    assert pp.is_infinite(p)
    assert (p[0], p[1]) == pytest.approx((0.0, 1.0))   # vertical direction


def test_crossing_lines_meet_at_a_finite_point():
    p = pp.meet(pp.hline(1, 0, -4), pp.hline(0, 1, -3))   # x = 4, y = 3
    assert not pp.is_infinite(p)
    assert (p[0], p[1]) == pytest.approx((4.0, 3.0))


def test_same_direction_points_at_infinity_are_equal():
    assert pp.same_point(pp.point_at_infinity(1, 2), pp.point_at_infinity(-2, -4))
    assert not pp.same_point(pp.point_at_infinity(1, 2), pp.point_at_infinity(1, 3))
    assert not pp.same_point(pp.point_at_infinity(1, 0), pp.hpoint(1, 0))


def test_join_and_incidence():
    line = pp.join(pp.hpoint(0, 0), pp.hpoint(2, 2))
    assert pp.incident(pp.hpoint(5, 5), line)
    assert not pp.incident(pp.hpoint(5, 4), line)
    assert pp.incident(pp.point_at_infinity(1, 1), line)          # parallel through the line
    assert not pp.incident(pp.point_at_infinity(1, 0), line)
    # line through a finite point and a point at infinity = the parallel through the point
    par = pp.join(pp.hpoint(0, 3), pp.point_at_infinity(1, 0))
    assert pp.same_line(par, pp.hline(0, 1, -3))
    # two different points at infinity span the line at infinity
    assert pp.join(pp.point_at_infinity(1, 0), pp.point_at_infinity(0, 1)).tolist() == [0.0, 0.0, 1.0]


# ---------------- 1: two-hinge continuous beam ----------------

def test_two_hinge_beam_contradiction_then_movable():
    r = run("structural.pole_plan", beam([0, 4, 7, 9, 14], {2: "hinge", 3: "hinge"},
                                         {0: {"kind": "pin"}, 1: {"kind": "roller"}, 4: {"kind": "pin"}}))
    assert (r.A, r.z, r.k, r.U) == (5, 4, 3, 0)
    assert r.counting == "U = (A + z) − 3k = (5 + 4) − 3·3 = 0"
    assert r.movable and r.dof == 1 and r.rules_agree
    assert r.verdict == "Movable → statically unusable (body 1 immovable)"
    assert [c["pole"] for c in r.contradictions] == ["(1)"]
    assert r.contradictions[0]["body"] == 1
    assert [b["immovable"] for b in r.bodies] == [True, False, False]
    assert xy(pole(r, "(2)")) == pytest.approx((7, 0))
    assert xy(pole(r, "(2,3)")) == pytest.approx((9, 0))
    assert xy(pole(r, "(3)")) == pytest.approx((14, 0))
    assert all(pole(r, n)["source"] == "rule" for n in ("(2)", "(2,3)", "(3)"))
    assert not any(p["name"] == "(1)" for p in r.poles)
    assert len(r.loci) == 1 and r.loci[0]["poles"] == ["(2)", "(3)", "(2,3)"]
    assert r.loci[0]["label"] == "G.O. ②③(2,3)"
    assert r.loci[0]["direction"] == pytest.approx([1.0, 0.0])
    assert r.loci[0]["point"][1] == pytest.approx(0.0)
    assert any("R2 pin support" in s for s in r.steps) and any("R5 hinge" in s for s in r.steps)
    # mode: bodies 2 and 3 rotate about their supports, body 1 stays at rest, max displacement 1
    assert max(abs(c) for d in r.node_displacement.values() for c in d) == pytest.approx(1.0)
    assert r.node_displacement["n0"] == pytest.approx([0, 0])
    assert r.node_displacement["n4"] == pytest.approx([0, 0])
    motion = {m["id"]: m for m in r.body_motion}
    assert motion[1]["theta"] == pytest.approx(0, abs=1e-9)
    assert motion[2]["theta"] * motion[3]["theta"] < 0


# ---------------- 2: same beam with two rollers instead of the right pin ----------------

def test_beam_with_two_rollers_is_immovable():
    r = run("structural.pole_plan", beam([0, 4, 7, 9, 11, 14], {2: "hinge", 3: "hinge"},
                                         {0: {"kind": "pin"}, 1: {"kind": "roller"},
                                          4: {"kind": "roller"}, 5: {"kind": "roller"}}))
    assert r.U == 0 and not r.movable and r.dof == 0 and r.rules_agree
    assert r.verdict == "Immovable → statically usable"
    assert [c["pole"] for c in r.contradictions] == ["(1)", "(3)", "(2)"]
    third = r.contradictions[1]
    assert third["body"] == 3 and "infinity" in third["text"]
    assert all(b["immovable"] for b in r.bodies)
    assert r.body_motion == [] and r.node_displacement == {}


# ---------------- 3: sleeve ----------------

def test_beam_with_sleeve():
    r = run("structural.pole_plan", beam([0, 5, 10], {1: "sleeve"}, {0: {"kind": "pin"}, 2: {"kind": "roller"}}))
    assert r.U == -1 and (r.A, r.z, r.k) == (3, 2, 2)
    assert r.movable and r.dof == 1 and r.rules_agree
    p12, p2 = pole(r, "(1,2)"), pole(r, "(2)")
    assert p12["at_infinity"] and p12["direction"] == pytest.approx([0, 1])
    assert p2["at_infinity"] and p2["direction"] == pytest.approx([0, 1])
    assert xy(pole(r, "(1)")) == pytest.approx((0, 0))
    # exact mode: the right part translates horizontally, the left part stays at rest
    assert r.node_displacement["n2"] == pytest.approx([1, 0])
    assert r.node_displacement["n0"] == pytest.approx([0, 0])


def test_shear_joint_pole_direction_is_along_the_axis():
    r = run("structural.pole_plan", beam([0, 5, 10], {1: "shear"}, {0: {"kind": "pin"}, 2: {"kind": "roller", "angle": 90}}))
    p12 = pole(r, "(1,2)")
    assert p12["at_infinity"] and p12["direction"] == pytest.approx([1, 0])
    assert r.U == -1 and r.movable and r.rules_agree


# ---------------- 4: truss with two bands and two rods ----------------

def truss_two_bands():
    # upper band: bottom chord y=3 (x=0,2,4,6), top chord y=4 (x=1,3,5), Warren diagonals; pin at its left end
    # lower band: top chord y=1 (x=0,2,4), bottom chord y=0 (x=1,3); roller at its left end sliding vertically
    nodes = {"S0": (0, 3), "S1": (2, 3), "S2": (4, 3), "S3": (6, 3), "T0": (1, 4), "T1": (3, 4), "T2": (5, 4),
             "W0": (0, 1), "W1": (2, 1), "W2": (4, 1), "X0": (1, 0), "X1": (3, 0)}
    upper = [("S0", "S1"), ("S1", "S2"), ("S2", "S3"), ("T0", "T1"), ("T1", "T2"),
             ("S0", "T0"), ("T0", "S1"), ("S1", "T1"), ("T1", "S2"), ("S2", "T2"), ("T2", "S3")]
    rods = [("S3", "W1"), ("S2", "W2")]   # inclined bar and vertical bar
    lower = [("W0", "W1"), ("W1", "W2"), ("X0", "X1"), ("W0", "X0"), ("X0", "W1"), ("W1", "X1"), ("X1", "W2")]
    members = [{"id": f"m{i}", "a": a, "b": b} for i, (a, b) in enumerate(upper + rods + lower)]
    return {"nodes": [{"id": k, "x": x, "y": y, "joint": "hinge"} for k, (x, y) in nodes.items()],
            "members": members,
            "supports": [{"node": "S0", "kind": "pin"}, {"node": "W0", "kind": "roller", "angle": 90}]}


def test_truss_with_two_bands_and_two_rods():
    r = run("structural.pole_plan", truss_two_bands())
    assert r.k == 4
    assert [len(b["members"]) for b in r.bodies] == [11, 1, 1, 7]
    assert (r.A, r.z, r.U) == (3, 8, -1)
    assert r.movable and r.dof == 1 and r.rules_agree and not r.contradictions
    # (1,4): intersection of the inclined rod (S3-W1) and the vertical rod (x = 4)
    assert xy(pole(r, "(1,4)")) == pytest.approx((4, 2))
    assert xy(pole(r, "(1)")) == pytest.approx((0, 3))
    # (4) on the horizontal through the roller (y = 1) and on the line (1)-(1,4)
    p4 = pole(r, "(4)")
    assert p4["y"] == pytest.approx(1)
    assert (p4["y"] - 3) * (4 - 0) == pytest.approx((2 - 3) * (p4["x"] - 0))
    assert p4["x"] == pytest.approx(8)
    # the loci contain the line (1),(1,4),(4)
    assert any(set(["(1)", "(1,4)", "(4)"]) <= set(g["poles"]) for g in r.loci)
    assert all(pole(r, n)["source"] == "rule" for n in ("(1)", "(1,4)", "(4)"))


# ---------------- 5: three-hinged arch ----------------

def arch(crown_y):
    return {"nodes": [{"id": "A", "x": 0, "y": 0}, {"id": "C", "x": 5, "y": crown_y, "joint": "hinge"},
                      {"id": "B", "x": 10, "y": 0}],
            "members": [{"id": "left", "a": "A", "b": "C"}, {"id": "right", "a": "C", "b": "B"}],
            "supports": [{"node": "A", "kind": "pin"}, {"node": "B", "kind": "pin"}]}


def test_three_hinged_arch_is_immovable():
    r = run("structural.pole_plan", arch(4.0))
    assert r.U == 0 and r.k == 2 and not r.movable and r.dof == 0 and r.rules_agree
    assert r.contradictions and all(b["immovable"] for b in r.bodies)


def test_three_hinged_arch_with_collinear_hinges_is_movable():
    r = run("structural.pole_plan", arch(0.0))
    assert r.U == 0 and r.movable and r.dof == 1 and r.rules_agree
    assert not r.contradictions
    assert xy(pole(r, "(1,2)")) == pytest.approx((5, 0))


# ---------------- 6: four-bar linkage ----------------

def test_four_bar_linkage():
    m = {"nodes": [{"id": "A", "x": 0, "y": 0, "joint": "hinge"}, {"id": "B", "x": 1, "y": 3, "joint": "hinge"},
                   {"id": "C", "x": 5, "y": 3, "joint": "hinge"}, {"id": "D", "x": 4, "y": 0, "joint": "hinge"}],
         "members": [{"id": "crank1", "a": "A", "b": "B"}, {"id": "coupler", "a": "B", "b": "C"},
                     {"id": "crank2", "a": "C", "b": "D"}],
         "supports": [{"node": "A", "kind": "pin"}, {"node": "D", "kind": "pin"}]}
    r = run("structural.pole_plan", m)
    assert r.k == 3 and r.U == -1 and r.movable and r.dof == 1 and r.rules_agree
    assert xy(pole(r, "(1)")) == pytest.approx((0, 0))
    assert xy(pole(r, "(1,2)")) == pytest.approx((1, 3))
    # the supports A, D and the coupler B-C are parallel (y = 0 and y = 3): (1,3) is at infinity, horizontal
    assert pole(r, "(1,3)")["at_infinity"] and pole(r, "(1,3)")["direction"] == pytest.approx([1, 0])


# ---------------- 7 / 8: rigid structures ----------------

def test_portal_frame_with_fixed_feet():
    m = {"nodes": [{"id": "A", "x": 0, "y": 0}, {"id": "B", "x": 0, "y": 4}, {"id": "C", "x": 6, "y": 4},
                   {"id": "D", "x": 6, "y": 0}],
         "members": [{"id": "col1", "a": "A", "b": "B"}, {"id": "beam", "a": "B", "b": "C"},
                     {"id": "col2", "a": "D", "b": "C"}],
         "supports": [{"node": "A", "kind": "fixed"}, {"node": "D", "kind": "fixed"}]}
    r = run("structural.pole_plan", m)
    assert (r.k, r.A, r.z, r.U) == (1, 6, 0, 3)
    assert not r.movable and r.dof == 0 and r.rules_agree and not r.contradictions
    assert r.bodies[0]["immovable"] and "R1" in r.bodies[0]["reason"]


def test_hinged_triangle_merges_to_one_body():
    nodes = [{"id": "A", "x": 0, "y": 0, "joint": "hinge"}, {"id": "B", "x": 4, "y": 0, "joint": "hinge"},
             {"id": "C", "x": 2, "y": 3, "joint": "hinge"}]
    members = [{"id": "ab", "a": "A", "b": "B"}, {"id": "bc", "a": "B", "b": "C"}, {"id": "ca", "a": "C", "b": "A"}]
    sup = [{"node": "A", "kind": "pin"}, {"node": "B", "kind": "roller"}]
    r = run("structural.pole_plan", {"nodes": nodes, "members": members, "supports": sup})
    assert r.k == 1 and (r.A, r.z, r.U) == (3, 0, 0)
    assert not r.movable and r.rules_agree
    assert len(r.bodies[0]["members"]) == 3
    # a vertical roller puts the roller line through the pin: the triangle may turn about A
    sup[1]["angle"] = 90
    r2 = run("structural.pole_plan", {"nodes": nodes, "members": members, "supports": sup})
    assert r2.movable and r2.dof == 1 and r2.rules_agree and r2.U == 0


# ---------------- sliding clamp, hinge with support, rods ----------------

def test_sliding_clamp_pole_at_infinity():
    # cantilever with a sliding clamp (translates vertically) and a vertical roller at the tip: still movable
    r = run("structural.pole_plan", beam([0, 4], {}, {0: {"kind": "clamp", "angle": 90}, 1: {"kind": "roller", "angle": 90}}))
    p = pole(r, "(1)")
    assert r.movable and r.rules_agree
    assert p["at_infinity"] and p["direction"] == pytest.approx([1, 0])


def test_pin_at_a_hinge_gives_both_bodies_the_pole_there():
    m = beam([0, 4, 8], {1: "hinge"}, {1: {"kind": "pin"}, 0: {"kind": "roller", "angle": 90}, 2: {"kind": "roller", "angle": 90}})
    r = run("structural.pole_plan", m)
    assert (r.A, r.z, r.k) == (4, 2, 2)
    assert xy(pole(r, "(1)")) == pytest.approx((4, 0)) and xy(pole(r, "(2)")) == pytest.approx((4, 0))
    assert r.rules_agree


def test_rule_verdict_matches_exact_dof_on_random_pinned_chains():
    rng = np.random.default_rng(3)
    for _ in range(25):
        pts = rng.uniform(0, 10, size=(5, 2))
        nodes = [{"id": f"n{i}", "x": float(p[0]), "y": float(p[1]), "joint": "hinge"} for i, p in enumerate(pts)]
        members = [{"id": f"m{i}", "a": f"n{i}", "b": f"n{i + 1}"} for i in range(4)]
        sup = [{"node": "n0", "kind": "pin"}, {"node": "n4", "kind": "pin"}]
        r = run("structural.pole_plan", {"nodes": nodes, "members": members, "supports": sup})
        assert r.U == -2 and r.movable and r.dof == 2 and r.rules_agree


# ---------------- validation ----------------

BASE = {"nodes": [{"id": "a", "x": 0, "y": 0}, {"id": "b", "x": 1, "y": 0}, {"id": "c", "x": 2, "y": 0}],
        "members": [{"id": "m1", "a": "a", "b": "b"}, {"id": "m2", "a": "b", "b": "c"}],
        "supports": [{"node": "a", "kind": "pin"}]}


def bad(**changes):
    return {**BASE, **changes}


@pytest.mark.parametrize("inputs, text", [
    ({"nodes": [], "members": [], "supports": []}, "at least one member"),
    (bad(nodes=BASE["nodes"] + [{"id": "a", "x": 5, "y": 0}]), "Duplicate node"),
    (bad(members=[BASE["members"][0], {"id": "m1", "a": "b", "b": "c"}]), "Duplicate member"),
    (bad(members=[{"id": "m1", "a": "a", "b": "zz"}]), "unknown node"),
    (bad(supports=[{"node": "zz", "kind": "pin"}]), "unknown node"),
    (bad(nodes=[{"id": "a", "x": 0, "y": 0}, {"id": "b", "x": 0, "y": 0}, {"id": "c", "x": 2, "y": 0}]), "zero length"),
    (bad(nodes=[{"id": "a", "x": 0, "y": 0}, {"id": "b", "x": 1, "y": 0, "joint": "sleeve"},
                {"id": "c", "x": 2, "y": 1}]), "collinear"),
    (bad(nodes=[{"id": "a", "x": 0, "y": 0, "joint": "shear"}, {"id": "b", "x": 1, "y": 0}, {"id": "c", "x": 2, "y": 0}]),
     "exactly two members"),
    (bad(nodes=BASE["nodes"] + [{"id": "d", "x": 9, "y": 9}]), "no member"),
    (bad(nodes=[{"id": "a", "x": 0, "y": 0}, {"id": "b", "x": 1, "y": 0, "joint": "sleeve"}, {"id": "c", "x": 2, "y": 0}],
         supports=[{"node": "b", "kind": "pin"}]), "neighbouring node"),
])
def test_validation_errors(inputs, text):
    with pytest.raises(ValueError, match=text):
        run("structural.pole_plan", inputs)


def test_fixed_support_at_a_hinge_between_bodies_is_rejected():
    m = beam([0, 4, 8], {1: "hinge"}, {1: {"kind": "fixed"}})
    with pytest.raises(ValueError, match="ambiguous"):
        run("structural.pole_plan", m)


# ---------------- registry ----------------

def test_tool_pole_plan():
    # JSON-like inputs, exactly as the web app sends them
    inputs = {
        "nodes": [{"id": "A", "x": 0, "y": 0, "joint": "rigid"}, {"id": "B", "x": 4, "y": 0, "joint": "rigid"},
                  {"id": "G1", "x": 7, "y": 0, "joint": "hinge"}, {"id": "G2", "x": 9, "y": 0, "joint": "hinge"},
                  {"id": "C", "x": 14, "y": 0, "joint": "rigid"}],
        "members": [{"id": "m1", "a": "A", "b": "B"}, {"id": "m2", "a": "B", "b": "G1"},
                    {"id": "m3", "a": "G1", "b": "G2"}, {"id": "m4", "a": "G2", "b": "C"}],
        "supports": [{"node": "A", "kind": "pin", "angle": 0}, {"node": "B", "kind": "roller", "angle": 0},
                     {"node": "C", "kind": "pin", "angle": 0}],
    }
    r = run("structural.pole_plan", inputs)
    assert r.movable and r.dof == 1 and r.U == 0 and r.rules_agree
    d = r.to_dict()
    for name in ("verdict", "movable", "dof", "U", "A", "z", "k", "counting", "rules_agree", "bodies", "poles", "loci",
                 "contradictions", "steps", "node_displacement", "body_motion"):
        assert name in d
    assert r.summary()["Kinematically movable"] is True
    # defaults run too (the example beam), and the tool is flagged for its own web page
    assert run("structural.pole_plan").verdict == r.verdict
    from engtoolkit import get_tool
    assert get_tool("structural.pole_plan").schema()["custom_page"] is True
    assert not math.isnan(sum(m["theta"] for m in r.body_motion))
