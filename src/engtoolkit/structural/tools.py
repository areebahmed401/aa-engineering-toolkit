"""Structural tools registered for the notebooks and the web app (inputs in SI units)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from engtoolkit.core.registry import Input, register_tool
from engtoolkit.core.results import Result, rfield
from engtoolkit.materials import get_material

from . import charts as _charts
from .analysis import BeamAnalysisResult, analyze_beam
from .loads import DistributedLoad, MomentLoad, PointLoad, support
from .sections import (
    Beam, CBeam, Circle, CrossSection, HollowCircle, IBeam, LBeam, Rectangle, RectangularTube, SectionProperties,
    TBeam, ZBeam,
)
from .torsion import Torsion, saint_venant_twist

ShapeName = Literal["rectangle", "square_tube", "rectangular_tube", "circle", "hollow_circle",
                    "i_beam", "c_beam", "t_beam", "z_beam", "l_beam", "profile"]


# Which SectionInputs dimensions each shape uses, with the label the dimension has for that shape.
# Exported in the schema (json_schema_extra "shape_fields", as ordered [name, label] pairs since pydantic
# sorts the keys of schema extras) so the web app shows only the relevant inputs.
SHAPE_FIELDS: dict[str, dict[str, str]] = {
    "rectangle": {"width": "Width b", "height": "Height h"},
    "square_tube": {"width": "Outer width b", "thickness": "Wall thickness t"},
    "rectangular_tube": {"width": "Outer width b", "height": "Outer height h", "thickness": "Wall thickness t"},
    "circle": {"radius": "Radius r"},
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
    "circle": "Circle", "hollow_circle": "Hollow circle", "i_beam": "I-beam", "c_beam": "Channel (C)",
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
               tags=("beam", "FEM", "bending"), custom_page=True, charts=_charts.beam_charts)
def beam_analysis_tool(inp: BeamAnalysisInputs) -> BeamAnalysisResult:
    return analyze_beam(build_beam(inp), theory=inp.theory, n_elem=inp.n_elem)


# ---------------- torsion ----------------

@dataclass
class TorsionResult(Result):
    twist: float = rfield("rad", "Twist at position")
    twist_deg: float = rfield("deg", "Twist at position")
    twist_saint_venant: float = rfield("rad", "Twist if warping were free (Saint-Venant)")
    max_shear_stress: float = rfield("Pa", "Max Saint-Venant shear stress (T/Wt)")
    alpha: float = rfield("", "Warping parameter α (0 = full warping, large = Saint-Venant)", default=math.nan)
    saint_venant_share: float = rfield("", "Torque share carried by Saint-Venant shear at the support", default=math.nan)


class TorsionInputs(BaseModel):
    section: SectionInputs = Field(default_factory=SectionInputs)
    material: str = Input("Steel", "", "Material", json_schema_extra={"choices": "materials:metal"})
    length: float = Input(1.0, "m", "Cantilever length", gt=0)
    torque: float = Input(200.0, "N·m", "End torque")
    position: float = Input(1.0, "m", "Position of interest from the fixed end", ge=0)


@register_tool("structural.torsion", "Torsion and warping (cantilever)", TorsionInputs,
               description="Twist of a cantilever under end torque: warping torsion for open sections, Saint-Venant otherwise.",
               reference="Vlasov warping torsion closed form θ(L) = TL/GJ·(1 − tanh α/α); Saint-Venant θ = TL/GJ",
               tags=("torsion", "warping"),
               charts=lambda inp, res: _charts.torsion_charts(
                   Beam(inp.material, inp.length, build_section(inp.section)), inp.torque, res))
def torsion_tool(inp: TorsionInputs) -> TorsionResult:
    section = build_section(inp.section)
    b = Beam(inp.material, inp.length, section)
    sv = saint_venant_twist(inp.torque, inp.position, b.material.G, section.J_torsion)
    tau = abs(inp.torque) / section.W_torsion
    if section.C_torsion > 0:
        t = Torsion(b, inp.torque, inp.position)
        theta = t.theta()
        return TorsionResult(theta, math.degrees(theta), sv, tau, t.alpha, t.saint_venant_share(0.0))
    return TorsionResult(sv, math.degrees(sv), sv, tau, math.nan, 1.0)
