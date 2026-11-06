"""Structural tools registered for the notebooks and the web app (inputs in SI units)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field

from engtoolkit.core.registry import Input, register_tool
from engtoolkit.core.results import Result, rfield
from engtoolkit.materials import get_material

from . import charts as _charts
from .analysis import BeamAnalysisResult, analyze_beam
from .kinematics import PolePlanInputs
from .loads import DistributedLoad, MomentLoad, PointLoad, support
from .polplan import PolePlanResult, analyze_pole_plan
from .sections import (
    Beam, CBeam, Circle, CrossSection, Ellipse, HollowCircle, IBeam, LBeam, Rectangle, RectangularTube,
    SectionProperties, TBeam, ZBeam,
)
from .thin_walled import ShearFlowResult, sectorial, shear_flow
from .torsion import solve_torsion

ShapeName = Literal["rectangle", "square_tube", "rectangular_tube", "circle", "ellipse", "hollow_circle",
                    "i_beam", "c_beam", "t_beam", "z_beam", "l_beam", "profile"]


# Which SectionInputs dimensions each shape uses, with the label the dimension has for that shape.
# Exported in the schema (json_schema_extra "shape_fields", as ordered [name, label] pairs since pydantic
# sorts the keys of schema extras) so the web app shows only the relevant inputs.
SHAPE_FIELDS: dict[str, dict[str, str]] = {
    "rectangle": {"width": "Width b", "height": "Height h"},
    "square_tube": {"width": "Outer width b", "thickness": "Wall thickness t"},
    "rectangular_tube": {"width": "Outer width b", "height": "Outer height h", "thickness": "Wall thickness t"},
    "circle": {"radius": "Radius r"},
    "ellipse": {"width": "Semi-axis a (horizontal)", "height": "Semi-axis b (vertical)"},
    "hollow_circle": {"radius": "Outer radius r", "inner_radius": "Inner radius ri"},
    "i_beam": {"width": "Flange width b", "thickness": "Flange thickness tf",
               "height": "Clear web height hw", "web_thickness": "Web thickness tw"},
    "c_beam": {"width": "Flange width b", "thickness": "Flange thickness tf",
               "height": "Clear web height hw", "web_thickness": "Web thickness tw"},
    "t_beam": {"width": "Flange width b", "thickness": "Flange thickness tf",
               "height": "Web height hw", "web_thickness": "Web thickness tw"},
    "z_beam": {"width": "Flange width b", "thickness": "Flange thickness tf",
               "height": "Clear web height hw", "web_thickness": "Web thickness tw"},
    "l_beam": {"width": "Leg length b", "thickness": "Leg thickness t"},
    "profile": {"profile": "Catalog profile"},
}
SHAPE_LABELS: dict[str, str] = {
    "rectangle": "Rectangle", "square_tube": "Square tube", "rectangular_tube": "Rectangular tube",
    "circle": "Circle", "ellipse": "Ellipse", "hollow_circle": "Hollow circle", "i_beam": "I-beam", "c_beam": "Channel (C)",
    "t_beam": "T-section", "z_beam": "Z-section", "l_beam": "Equal angle (L)", "profile": "Catalog IPE",
}


class SectionInputs(BaseModel):
    shape: ShapeName = Input("i_beam", "", "Section shape",
                             json_schema_extra={"shape_fields": {k: [list(p) for p in v.items()]
                                                                 for k, v in SHAPE_FIELDS.items()},
                                                "shape_labels": SHAPE_LABELS})
    profile: str = Input("IPE 200", "", "Catalog profile (shape = profile)", json_schema_extra={"choices": "profiles"})
    width: float = Input(0.1, "m", "Width / outer width / flange width / leg length", gt=0)
    height: float = Input(0.2, "m", "Height / outer height / clear web height", gt=0)
    thickness: float = Input(0.01, "m", "Wall / flange / leg thickness", gt=0)
    web_thickness: float = Input(0.006, "m", "Web thickness", gt=0)
    radius: float = Input(0.05, "m", "Outer radius (circles)", gt=0)
    inner_radius: float = Input(0.04, "m", "Inner radius (hollow circle)", gt=0)


def build_section(s: SectionInputs) -> CrossSection:
    if s.shape == "rectangle":
        return Rectangle(s.width, s.height)
    if s.shape == "square_tube":
        return RectangularTube(s.width, s.width, s.thickness)
    if s.shape == "rectangular_tube":
        return RectangularTube(s.width, s.height, s.thickness)
    if s.shape == "circle":
        return Circle(s.radius)
    if s.shape == "ellipse":
        return Ellipse(s.width, s.height)
    if s.shape == "hollow_circle":
        return HollowCircle(s.radius, s.inner_radius)
    if s.shape == "l_beam":
        return LBeam(s.width, s.thickness)
    if s.shape == "profile":
        return IBeam.from_profile(s.profile)
    cls = {"i_beam": IBeam, "c_beam": CBeam, "t_beam": TBeam, "z_beam": ZBeam}[s.shape]
    return cls(s.width, s.thickness, s.height, s.web_thickness)


# ---------------- section properties ----------------

class SectionPropertiesInputs(SectionInputs):
    material: str = Input("Steel", "", "Material (for mass)", json_schema_extra={"choices": "materials:metal"})


@register_tool("structural.section_properties", "Section properties", SectionPropertiesInputs,
               description="Area, second moments, section modulus, torsion and warping constants, centroid and shear centre.",
               reference="Gere & Goodno, Mechanics of Materials; Roark's Formulas (torsion); thin-walled theory (shear centre, warping)",
               tags=("section", "beam", "properties"), custom_page=True,
               charts=lambda inp, res: _charts.section_charts(build_section(inp)))
def section_properties_tool(inp: SectionPropertiesInputs) -> SectionProperties:
    return build_section(inp).properties(rho=get_material(inp.material).rho)


# ---------------- beam analysis ----------------

class LoadInput(BaseModel):
    kind: Literal["point", "udl", "moment"] = Input("point", "", "Load type")
    value: float = Input(10e3, "", "P [N] (down +), w [N/m] (down +) or M [N·m] (CCW +)")
    x: float = Input(1.0, "m", "Position (start for UDL)", ge=0)
    x_end: float | None = Input(None, "m", "UDL end (blank = beam end)")


class BeamAnalysisInputs(BaseModel):
    section: SectionInputs = Field(default_factory=SectionInputs)
    material: str = Input("Steel", "", "Material", json_schema_extra={"choices": "materials:metal"})
    length: float = Input(2.0, "m", "Span", gt=0)
    left_support: Literal["fixed", "pinned", "roller", "free"] = Input("fixed", "", "Left support")
    right_support: Literal["fixed", "pinned", "roller", "free"] = Input("free", "", "Right support")
    loads: list[LoadInput] = Field(default_factory=lambda: [LoadInput()])
    theory: Literal["EB", "TB"] = Input("EB", "", "Beam theory (EB = Euler-Bernoulli, TB = Timoshenko)")
    n_elem: int = Input(200, "", "FEM elements", ge=4, le=2000)


def build_beam(inp: BeamAnalysisInputs) -> Beam:
    b = Beam(inp.material, inp.length, build_section(inp.section))
    b.set_end_conditions(support(inp.left_support), support(inp.right_support))
    for load in inp.loads:
        if load.x > inp.length or (load.x_end is not None and load.x_end > inp.length):
            raise ValueError(f"Load position beyond the span ({inp.length} m)")
        if load.kind == "point":
            b.add_load(PointLoad(load.value, load.x))
        elif load.kind == "udl":
            b.add_load(DistributedLoad(load.value, load.x, load.x_end))
        else:
            b.add_load(MomentLoad(load.value, load.x))
    return b


@register_tool("structural.beam_analysis", "Beam analysis", BeamAnalysisInputs,
               description="Determinacy check, then equilibrium or 2D FEM: reactions, deflection, shear, moment and stress.",
               reference="Closed-form beam tables (Roark; Gere & Goodno): PL³/3EI, 5wL⁴/384EI, wL²/8, wL²/12",
               tags=("beam", "FEM", "bending"), custom_page=True,
               charts=lambda inp, res: _charts.beam_charts(inp, res, build_section(inp.section)))
def beam_analysis_tool(inp: BeamAnalysisInputs) -> BeamAnalysisResult:
    return analyze_beam(build_beam(inp), theory=inp.theory, n_elem=inp.n_elem)


# ---------------- drawn thin-walled sections (shear flow, torsion) ----------------

class NodeInput(BaseModel):
    x2: float = Input(0.0, "m", "x2 (horizontal, right +)")
    x3: float = Input(0.0, "m", "x3 (vertical, down +)")


class WallInput(BaseModel):
    i: int = Input(0, "", "Start node i (s runs i → j)", ge=0)
    j: int = Input(1, "", "End node j", ge=0)
    h: float = Input(0.002, "m", "Wall thickness h", gt=0)
    G: float = Input(81e9, "Pa", "Shear modulus G", gt=0)


def _channel_nodes() -> list[NodeInput]:
    # Channel: 100 mm web, 50 mm flanges opening to +x2 (x3 points down)
    return [NodeInput(x2=0.05, x3=0.0), NodeInput(x2=0.0, x3=0.0), NodeInput(x2=0.0, x3=0.1),
            NodeInput(x2=0.05, x3=0.1)]


def _channel_walls() -> list[WallInput]:
    return [WallInput(i=0, j=1), WallInput(i=1, j=2), WallInput(i=2, j=3)]


# ---------------- torsion ----------------

class TorqueLoadInput(BaseModel):
    x: float = Input(1.0, "m", "Position from the left end", ge=0)
    T: float = Input(200.0, "N·m", "Point torque (about +x1)")


@dataclass
class TorsionResult(Result):
    twist: float = rfield("rad", "Twist at position")
    twist_deg: float = rfield("deg", "Twist at position")
    twist_saint_venant: float = rfield("rad", "Twist if warping were free (Saint-Venant)")
    max_shear_stress: float = rfield("Pa", "Max shear stress if all torque were Saint-Venant (max |T|/W_T)")
    alpha: float = rfield("", "Warping parameter α (0 = full warping, large = Saint-Venant)", default=math.nan)
    saint_venant_share: float = rfield("", "Torque share carried by Saint-Venant shear at the support", default=math.nan)
    mode: str = rfield("", "Warping (free or restrained)", default="restrained")
    J_T: float = rfield("m^4", "Torsion constant J_T", default=math.nan)
    W_T: float = rfield("m^3", "Torsional section modulus W_T", default=math.nan)
    C_T: float = rfield("m^6", "Warping constant C_T", default=0.0)
    omega_max: float = rfield("m^2", "Max |ω| (principal sectorial coordinate)", default=math.nan)
    mu: float = rfield("", "Load parameter μ = T L³/(E C_T), T = max |T(x)|", default=math.nan)
    twist_rate_sv: float = rfield("rad/m", "Saint-Venant ϑ' = T/(G J_T), T = max |T(x)|", default=math.nan)
    theta_max: float = rfield("rad", "Twist of largest magnitude", default=math.nan)
    x_theta_max: float = rfield("m", "Position of the largest twist", default=math.nan)
    M_sv_max: float = rfield("N·m", "Max |M_SV| (Saint-Venant torque)", default=math.nan)
    M_b_max: float = rfield("N·m", "Max |M_B| (warping torque)", default=0.0)
    B_max: float = rfield("N·m^2", "Max |bimoment B|", default=0.0)
    sigma_w_max: float = rfield("Pa", "Max |warping normal stress σ_ω| = B ω_max/C_T", default=0.0)
    tau_sv_max: float = rfield("Pa", "Max Saint-Venant shear stress |M_SV|/W_T", default=math.nan)
    T_left: float = rfield("N·m", "Internal torque at x = 0+", default=math.nan)
    T_right: float = rfield("N·m", "Internal torque at x = L−", default=math.nan)
    note: str = rfield("", "Note", default="")
    x: list = rfield("m", "Positions x (point-torque positions twice: left and right value)",
                     default_factory=list, summary=False)
    theta: list = rfield("rad", "Twist ϑ(x)", default_factory=list, summary=False)
    theta_sv: list = rfield("rad", "Twist with free warping (Saint-Venant only)", default_factory=list, summary=False)
    dtheta: list = rfield("rad/m", "Rate of twist ϑ'(x)", default_factory=list, summary=False)
    M_sv: list = rfield("N·m", "Saint-Venant torque M_SV = G J_T ϑ'", default_factory=list, summary=False)
    M_b: list = rfield("N·m", "Warping torque M_B = −E C_T ϑ'''", default_factory=list, summary=False)
    T_total: list = rfield("N·m", "Internal torque T = M_SV + M_B", default_factory=list, summary=False)
    bimoment: list = rfield("N·m^2", "Bimoment B = −E C_T ϑ''", default_factory=list, summary=False)
    sigma_w: list = rfield("Pa", "Warping normal stress B ω_max/C_T", default_factory=list, summary=False)
    tau_sv: list = rfield("Pa", "Saint-Venant shear stress |M_SV|/W_T", default_factory=list, summary=False)
    steps: list = rfield("", "Formulary steps", default_factory=list, summary=False)


class TorsionInputs(BaseModel):
    section: SectionInputs = Field(default_factory=SectionInputs)
    material: str = Input("Steel", "", "Material", json_schema_extra={"choices": "materials:metal"})
    length: float = Input(1.0, "m", "Member length", gt=0)
    torque: float = Input(200.0, "N·m", "Torque at x = L (used when no point torques are listed)")
    position: float = Input(1.0, "m", "Position of interest from the left end", ge=0)
    mode: Literal["free", "restrained"] = Input("restrained", "", "Warping: free (Saint-Venant) or restrained")
    section_source: Literal["library", "drawn"] = Input("library", "", "Section from the library or drawn")
    nodes: list[NodeInput] = Field(default_factory=_channel_nodes)
    walls: list[WallInput] = Field(default_factory=_channel_walls)
    eta3: float = Input(1.0, "", "η3 for a drawn open section (J_T = η3/3 Σ h³ l)", gt=0)
    left_support: Literal["fixed", "fork", "free"] = Input("fixed", "", "Left end (x = 0)")
    right_support: Literal["fixed", "fork", "free"] = Input("free", "", "Right end (x = L)")
    loads: list[TorqueLoadInput] = Field(default_factory=list)
    m_t: float = Input(0.0, "N·m/m", "Uniform distributed torque m_t (whole span)")
    Q2: float = Input(0.0, "N", "Free warping: transverse force Q2 (+x2) at x = L")
    Q3: float = Input(0.0, "N", "Free warping: transverse force Q3 (+x3, down) at x = L")
    e2: float = Input(0.0, "m", "Free warping: shear centre x2 minus load line x2")
    e3: float = Input(0.0, "m", "Free warping: shear centre x3 minus load line x3")


def torsion_section(inp: TorsionInputs, G: float) -> dict:
    """J_T, W_T, C_T, ω_max (+ extra steps, note) of the library or drawn section (drawn walls use ``G``)."""
    if inp.section_source == "library":
        sec = build_section(inp.section)
        out = {"J_T": sec.J_torsion, "W_T": sec.W_torsion, "C_T": sec.C_torsion, "omega_max": sec.omega_max,
               "steps": [], "note": ""}
        if isinstance(sec, RectangularTube):
            tw = sec.thick_wall_torsion()
            out["steps"] = [{"label": "J_TB (Bredt, mid-line box)", "value": tw["J_TB"], "unit": "m^4"},
                            {"label": "Σ J_Ti (walls as solid rectangles, η1)", "value": sum(tw["J_walls"]),
                             "unit": "m^4"},
                            {"label": "Bredt share T_B/T = J_TB/J_T", "value": tw["share_B"], "unit": ""}]
        return out
    nodes = [(n.x2, n.x3) for n in inp.nodes]
    walls = [(w.i, w.j, w.h, G) for w in inp.walls]
    sf = shear_flow(nodes, walls, Q2=0.0, Q3=0.0, Mt=1.0)
    if sf.n_cells:
        steps = [{"label": f"A_cell {k}", "value": a, "unit": "m^2"} for k, a in enumerate(sf.A_cell)]
        return {"J_T": sf.J_T, "W_T": 1 / sf.tau_max, "C_T": 0.0, "omega_max": math.nan, "steps": steps,
                "note": "Closed drawn section: J_T from Bredt (multi-cell), C_T taken as 0. "}
    sw = sectorial(nodes, walls)
    h = np.array([w.h for w in inp.walls])
    P = np.array(nodes)
    l = np.hypot(*(P[[w.j for w in inp.walls]] - P[[w.i for w in inp.walls]]).T)
    J_T = inp.eta3 / 3 * float(np.sum(h**3 * l))
    return {"J_T": J_T, "W_T": J_T / float(h.max()), "C_T": sw.C_T, "omega_max": sw.omega_max,
            "steps": [{"label": "Shear centre x2 (pole of ω)", "value": sw.x2_SC, "unit": "m"},
                      {"label": "Shear centre x3 (pole of ω)", "value": sw.x3_SC, "unit": "m"}], "note": ""}


def _torsion_chart_section(inp: TorsionInputs):
    if inp.section_source == "library":
        return build_section(inp.section)
    nodes = [(n.x2, n.x3) for n in inp.nodes]
    sf = shear_flow(nodes, [(w.i, w.j, w.h) for w in inp.walls], Q2=0.0, Q3=0.0)
    return {"nodes": nodes, "walls": [(w.i, w.j) for w in inp.walls], "SC": (sf.x2_SC, sf.x3_SC)}


@register_tool("structural.torsion", "Torsion (free and restrained warping)", TorsionInputs,
               description="Twist, Saint-Venant and warping torque, bimoment and stresses of a member under point "
                           "and distributed torques, with fixed, fork or free ends.",
               reference="RWTH OLS formulary §3: Saint-Venant ϑ' = T/(G J_T), τ = T/W_T; warping torsion "
                         "E C_T ϑ'''' − G J_T ϑ'' = m_t, T = M_SV + M_B, σ_ω = B ω/C_T",
               tags=("torsion", "warping", "bimoment"), custom_page=True,
               charts=lambda inp, res: _charts.torsion_charts(res, _torsion_chart_section(inp)))
def torsion_tool(inp: TorsionInputs) -> TorsionResult:
    """
    Free warping (mode "free"): Saint-Venant only, G J_T ϑ'' = −m_t with the same supports. Restrained warping:
    E C_T ϑ'''' − G J_T ϑ'' = m_t (falls back to Saint-Venant when C_T = 0). Point torques ``loads``, or the
    legacy ``torque`` at x = L when the list is empty. In free mode a transverse force (Q2, Q3) at x = L whose
    load line is offset from the shear centre adds T = Q2 e3 − Q3 e2 at x = L (e = shear centre − load line).
    """
    L = inp.length
    if inp.position > L:
        raise ValueError(f"Position must be between 0 and {L} m")
    mat = get_material(inp.material)
    G, E = mat.G, mat.E
    sec = torsion_section(inp, G)
    J_T, W_T, C_T, om = sec["J_T"], sec["W_T"], sec["C_T"], sec["omega_max"]
    GJ, EC = G * J_T, E * C_T
    loads = [(ld.x, ld.T) for ld in inp.loads] or [(L, inp.torque)]
    note = sec["note"]
    if inp.mode == "free" and (inp.Q2 * inp.e3 - inp.Q3 * inp.e2):
        loads.append((L, inp.Q2 * inp.e3 - inp.Q3 * inp.e2))
    restrained = inp.mode == "restrained" and EC > 0
    if inp.mode == "restrained" and not EC > 0:
        note += "C_T = 0 (closed or solid section): warping restraint has no effect, solved as free warping."
    args = dict(left=inp.left_support, right=inp.right_support, point_torques=loads, m_t=inp.m_t)
    sv = solve_torsion(L, GJ, 0.0, **args)
    sol = solve_torsion(L, GJ, EC, **args) if restrained else sv

    T = sol.T
    k_T = int(np.argmax(np.abs(T)))
    T_ref = float(T[k_T])
    alpha = math.sqrt(GJ * L**2 / EC) if EC > 0 else math.nan
    mu = T_ref * L**3 / EC if EC > 0 else math.nan
    if restrained:
        end = 0 if inp.left_support != "free" else -1
        share = float(sol.M_sv[end] / T[end]) if abs(T[end]) > 1e-12 * max(abs(T_ref), 1e-300) else math.nan
        sigma_w = sol.B * om / C_T
    else:
        share = 1.0
        sigma_w = np.zeros_like(T)
    tau_sv = np.abs(sol.M_sv) / W_T
    k_th = int(np.argmax(np.abs(sol.theta)))
    theta = sol.at(inp.position)["theta"]
    sw_max = float(np.max(np.abs(sigma_w))) if np.all(np.isfinite(sigma_w)) else math.nan
    res = TorsionResult(
        twist=theta, twist_deg=math.degrees(theta), twist_saint_venant=sv.at(inp.position)["theta"],
        max_shear_stress=abs(T_ref) / W_T, alpha=alpha, saint_venant_share=share, mode=inp.mode,
        J_T=J_T, W_T=W_T, C_T=C_T, omega_max=om, mu=mu, twist_rate_sv=T_ref / GJ,
        theta_max=float(sol.theta[k_th]), x_theta_max=float(sol.x[k_th]),
        M_sv_max=float(np.max(np.abs(sol.M_sv))), M_b_max=float(np.max(np.abs(sol.M_b))),
        B_max=float(np.max(np.abs(sol.B))), sigma_w_max=sw_max, tau_sv_max=float(np.max(tau_sv)),
        T_left=float(T[0]), T_right=float(T[-1]), note=note.strip(),
        x=sol.x.tolist(), theta=sol.theta.tolist(), theta_sv=sv.theta.tolist(), dtheta=sol.dtheta.tolist(),
        M_sv=sol.M_sv.tolist(), M_b=sol.M_b.tolist(), T_total=T.tolist(), bimoment=sol.B.tolist(),
        sigma_w=sigma_w.tolist(), tau_sv=tau_sv.tolist(),
    )
    steps = [("J_T (torsion constant)", J_T, "m^4"), ("W_T (torsional section modulus)", W_T, "m^3")]
    steps += [(st["label"], st["value"], st["unit"]) for st in sec["steps"]]
    steps += [("C_T (warping constant)", C_T, "m^6"), ("ω_max (principal sectorial coordinate)", om, "m^2"),
              ("α = L √(G J_T/(E C_T))", alpha, ""), ("μ = T L³/(E C_T)", mu, ""),
              ("ϑ' = T/(G J_T) (Saint-Venant)", res.twist_rate_sv, "rad/m"),
              ("T(0+)", res.T_left, "N·m"), ("T(L−)", res.T_right, "N·m"),
              ("ϑ at position", theta, "rad"), ("ϑ_max", res.theta_max, "rad"),
              ("max |M_SV|", res.M_sv_max, "N·m"), ("max |M_B|", res.M_b_max, "N·m"),
              ("max |B|", res.B_max, "N·m^2"), ("max |σ_ω| = B ω_max/C_T", sw_max, "Pa"),
              ("max τ_SV = |M_SV|/W_T", res.tau_sv_max, "Pa")]
    res.steps = [{"label": lb, "value": float(v), "unit": u} for lb, v, u in steps]
    return res


# ---------------- pole plan (kinematic movability) ----------------

@register_tool("structural.pole_plan", "Pole plan (kinematic movability)", PolePlanInputs,
               description="Counting criterion and pole plan (Polplan) of a planar system of rigid bodies, "
                           "checked against an exact small-displacement analysis.",
               reference="Pole rules of rigid-body kinematics (main-pole and relative-pole theorems); counting criterion U = (A + z) - 3k",
               tags=("kinematics", "pole plan", "mechanism", "stability"), custom_page=True)
def pole_plan_tool(inp: PolePlanInputs) -> PolePlanResult:
    return analyze_pole_plan(inp)


# ---------------- thin-walled shear flow ----------------

class ShearFlowInputs(BaseModel):
    nodes: list[NodeInput] = Field(default_factory=_channel_nodes)
    walls: list[WallInput] = Field(default_factory=_channel_walls)
    Q2: float = Input(0.0, "N", "Shear force Q2 (+x2)")
    Q3: float = Input(1000.0, "N", "Shear force Q3 (+x3, down)")
    load_at_shear_centre: bool = Input(True, "", "Load acts through the shear centre")
    a2: float = Input(0.0, "m", "Load line x2 (if not through the shear centre)")
    a3: float = Input(0.0, "m", "Load line x3 (if not through the shear centre)")
    Mt: float = Input(0.0, "N·m", "Torque M_t (about +x1, from x2 towards x3)")


@register_tool("structural.shear_flow", "Shear flow (thin-walled)", ShearFlowInputs,
               description="Shear flow t(s) and shear centre of open, branched, closed and multi-cell thin-walled sections.",
               reference="RWTH OLS formulary §2: t' = −Q3 S2/J22 (cut open), t0 from ϑ' = 0, Bredt M_t = 2 A t",
               tags=("section", "shear flow", "shear centre", "thin-walled"), custom_page=True)
def shear_flow_tool(inp: ShearFlowInputs) -> ShearFlowResult:
    return shear_flow([(n.x2, n.x3) for n in inp.nodes], [(w.i, w.j, w.h, w.G) for w in inp.walls],
                      Q2=inp.Q2, Q3=inp.Q3, Mt=inp.Mt,
                      load_point=None if inp.load_at_shear_centre else (inp.a2, inp.a3))
