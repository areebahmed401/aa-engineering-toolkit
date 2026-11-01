"""
ASME VIII-1 tools registered for the notebooks and the web app (inputs in SI units).

Preliminary sizing only: verify against the current edition of ASME BPVC Section VIII Division 1.
Allowable stresses S (Section II-D) and the UG-28 chart factor B are user inputs; no code tables
are reproduced.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from engtoolkit.core.registry import Input, register_tool
from engtoolkit.materials import get_material

from . import charts as _charts
from .div1.common import DISCLAIMER, JOINT_EFFICIENCIES, HydrotestResult, hydrotest_pressure
from .div1.external_pressure import ExternalPressureResult, external_pressure_cylinder
from .div1.heads import FLAT_HEAD_C, HeadResult, flat_head, formed_head
from .div1.nozzles import NozzleResult, nozzle_reinforcement
from .div1.report import Nozzle, VesselDesignResult, vessel_design
from .div1.shells import ShellResult, cylindrical_shell, spherical_shell

JointE = Literal[1.0, 0.85, 0.7, 0.9, 0.8, 0.65]
FlatC = Literal[0.17, 0.2, 0.25, 0.3, 0.33]
FormedKind = Literal["ellipsoidal_2_1", "ellipsoidal", "torispherical", "hemispherical"]
HeadKindInput = Literal["ellipsoidal_2_1", "ellipsoidal", "torispherical", "hemispherical", "flat"]
HostInput = Literal["cylinder", "sphere", "ellipsoidal_2_1", "torispherical", "hemispherical"]

E_HELP = "UW-12 joint efficiency: " + "; ".join(f"{k:g} = {v}" for k, v in JOINT_EFFICIENCIES.items())
C_HELP = "Fig. UG-34 attachment factor: " + "; ".join(f"{k:g} = {v}" for k, v in FLAT_HEAD_C.items())
S_HELP = "Allowable stress at design temperature from ASME II-D (user verified; not supplied by the toolkit)"
TAGS = ("pressure vessel", "ASME VIII-1")
REF_NOTE = " " + DISCLAIMER


def _modulus(material: str, T: float | None) -> float:
    m = get_material(material)
    try:
        return m.prop("E", T)
    except (ValueError, KeyError):
        return m.prop("E")


# ---------------- shells ----------------

class _PressureBase(BaseModel):
    P: float = Input(1.0e6, "Pa", "Internal design pressure", gt=0)
    D_inside: float = Input(1.2, "m", "Inside diameter (new)", gt=0)
    S: float = Input(138e6, "Pa", "Allowable stress S", S_HELP, gt=0)
    E: JointE = Input(0.85, "", "Joint efficiency E", E_HELP)
    corrosion: float = Input(3e-3, "m", "Corrosion allowance", ge=0)
    undertolerance: float = Input(0.0, "m", "Mill undertolerance", ge=0)
    t_nominal: float | None = Input(None, "m", "Nominal thickness (blank = next standard plate)", gt=0)


class CylindricalShellInputs(_PressureBase):
    E_circ: JointE | None = Input(None, "", "Circumferential joint efficiency (blank = E)", E_HELP)


@register_tool("asme.cylindrical_shell", "Cylindrical shell (UG-27)", CylindricalShellInputs,
               description="Required thickness and MAWP of a cylindrical shell under internal pressure "
                           "(circumferential and longitudinal stress, Appendix 1-2 when thick).",
               reference="ASME VIII-1 UG-27(c), Appendix 1-2; validated by hand calculation and against "
                         "Megyesy, Pressure Vessel Handbook (shell under internal pressure)." + REF_NOTE,
               tags=TAGS, charts=_charts.shell_charts)
def cylindrical_shell_tool(inp: CylindricalShellInputs) -> ShellResult:
    return cylindrical_shell(inp.P, inp.D_inside, inp.S, inp.E, inp.corrosion, inp.t_nominal, inp.E_circ,
                             inp.undertolerance)


class SphericalShellInputs(_PressureBase):
    pass


@register_tool("asme.spherical_shell", "Spherical shell (UG-27)", SphericalShellInputs,
               description="Required thickness and MAWP of a spherical shell under internal pressure.",
               reference="ASME VIII-1 UG-27(d), Appendix 1-3; validated by hand calculation." + REF_NOTE,
               tags=TAGS, charts=_charts.shell_charts)
def spherical_shell_tool(inp: SphericalShellInputs) -> ShellResult:
    return spherical_shell(inp.P, inp.D_inside, inp.S, inp.E, inp.corrosion, inp.t_nominal, inp.undertolerance)


# ---------------- heads ----------------

class FormedHeadInputs(_PressureBase):
    kind: FormedKind = Input("ellipsoidal_2_1", "", "Head type")
    E: JointE = Input(1.0, "", "Joint efficiency E (1.0 = seamless head)", E_HELP)
    ratio: float = Input(2.0, "", "Ellipsoidal D/2h (general ellipsoidal)", ge=1.0, le=3.0)
    crown_radius: float | None = Input(None, "m", "Torispherical crown radius L (blank = D)", gt=0)
    knuckle_radius: float | None = Input(None, "m", "Torispherical knuckle radius r (blank = 0.06 L)", gt=0)


@register_tool("asme.formed_head", "Formed head (UG-32)", FormedHeadInputs,
               description="2:1 ellipsoidal, general ellipsoidal (K), torispherical (6 % knuckle or factor M) "
                           "and hemispherical heads under internal pressure.",
               reference="ASME VIII-1 UG-32, Appendix 1-4; validated by hand calculation (K = 1 and M = 1.77 "
                         "reproduce the UG-32 formulas)." + REF_NOTE,
               tags=TAGS, charts=_charts.head_charts)
def formed_head_tool(inp: FormedHeadInputs) -> HeadResult:
    return formed_head(inp.P, inp.D_inside, inp.S, inp.kind, inp.E, inp.corrosion, inp.t_nominal, inp.ratio,
                       inp.crown_radius, inp.knuckle_radius, inp.undertolerance)


class FlatHeadInputs(BaseModel):
    P: float = Input(0.5e6, "Pa", "Internal design pressure", gt=0)
    d: float = Input(0.6, "m", "Diameter d (Fig. UG-34, new)", gt=0)
    S: float = Input(138e6, "Pa", "Allowable stress S", S_HELP, gt=0)
    C: FlatC = Input(0.33, "", "Attachment factor C", C_HELP)
    E: JointE = Input(1.0, "", "Joint efficiency E (butt joints in the head)", E_HELP)
    corrosion: float = Input(3e-3, "m", "Corrosion allowance", ge=0)
    W: float = Input(0.0, "N", "Bolt load W (bolted covers)", ge=0)
    h_G: float = Input(0.0, "m", "Gasket moment arm h_G (bolted covers)", ge=0)
    t_nominal: float | None = Input(None, "m", "Nominal thickness (blank = next standard plate)", gt=0)


@register_tool("asme.flat_head", "Flat head (UG-34)", FlatHeadInputs,
               description="Unstayed circular flat head or bolted cover, with the attachment factor C chosen "
                           "from the sketches of Fig. UG-34.",
               reference="ASME VIII-1 UG-34 eq. (1) and (2); validated by hand calculation." + REF_NOTE,
               tags=TAGS, charts=_charts.flat_head_charts)
def flat_head_tool(inp: FlatHeadInputs) -> HeadResult:
    return flat_head(inp.P, inp.d, inp.S, inp.C, inp.E, inp.corrosion, inp.t_nominal, inp.W, inp.h_G)


# ---------------- nozzle reinforcement ----------------

class NozzleReinforcementInputs(BaseModel):
    P: float = Input(1.0e6, "Pa", "Internal design pressure", gt=0)
    host: HostInput = Input("cylinder", "", "Opening in")
    D_host: float = Input(1.2, "m", "Host inside diameter (new)", gt=0)
    t_host: float = Input(10e-3, "m", "Host nominal thickness", gt=0)
    S_host: float = Input(138e6, "Pa", "Host allowable stress Sv", S_HELP, gt=0)
    crown_radius: float | None = Input(None, "m", "Crown radius L (torispherical host, blank = D)", gt=0)
    d_nozzle: float = Input(0.1541, "m", "Nozzle inside diameter (new)", gt=0)
    t_nozzle: float = Input(7.11e-3, "m", "Nozzle nominal wall", gt=0)
    S_nozzle: float | None = Input(None, "Pa", "Nozzle allowable stress Sn (blank = Sv)", gt=0)
    corrosion: float = Input(3e-3, "m", "Corrosion allowance", ge=0)
    pad_diameter: float = Input(0.3, "m", "Pad outside diameter Dp (0 = no pad)", ge=0)
    pad_thickness: float = Input(10e-3, "m", "Pad thickness te", ge=0)
    weld_leg_nozzle: float = Input(6e-3, "m", "Outward nozzle fillet weld leg", ge=0)
    weld_leg_pad: float = Input(6e-3, "m", "Pad outer fillet weld leg", ge=0)
    inward_projection: float = Input(0.0, "m", "Nozzle inward projection h", ge=0)


@register_tool("asme.nozzle_reinforcement", "Nozzle reinforcement (UG-37)", NozzleReinforcementInputs,
               description="Area-replacement check for a set-in nozzle with optional pad (simplified: F = 1, "
                           "outward fillet welds only, no UG-41 weld strength or UG-45 neck check).",
               reference="ASME VIII-1 UG-37, Fig. UG-37.1 area formulas; validated by hand calculation "
                         "(Moss, Pressure Vessel Design Manual, procedure for reinforcement of openings)." + REF_NOTE,
               tags=TAGS + ("nozzle",), charts=_charts.nozzle_charts)
def nozzle_reinforcement_tool(inp: NozzleReinforcementInputs) -> NozzleResult:
    return nozzle_reinforcement(inp.P, inp.host, inp.D_host, inp.t_host, inp.S_host, inp.d_nozzle, inp.t_nozzle,
                                inp.S_nozzle, inp.corrosion, pad_diameter=inp.pad_diameter,
                                pad_thickness=inp.pad_thickness, weld_leg_nozzle=inp.weld_leg_nozzle,
                                weld_leg_pad=inp.weld_leg_pad, inward_projection=inp.inward_projection,
                                crown_radius=inp.crown_radius)


# ---------------- external pressure ----------------

class ExternalPressureInputs(BaseModel):
    P_external: float = Input(101325.0, "Pa", "External design pressure (full vacuum = 101.3 kPa)", ge=0)
    Do: float = Input(1.22, "m", "Outside diameter Do", gt=0)
    L: float = Input(3.4, "m", "Design length L (UG-28(b): incl. 1/3 of each head depth)", gt=0)
    t_nominal: float = Input(10e-3, "m", "Nominal thickness", gt=0)
    corrosion: float = Input(3e-3, "m", "Corrosion allowance", ge=0)
    material: str = Input("Steel", "", "Material (elastic modulus)", json_schema_extra={"choices": "materials:metal"})
    T: float = Input(423.15, "K", "Design temperature (for E)")
    E_modulus: float | None = Input(None, "Pa", "Elastic modulus (blank = from material)", gt=0)
    factor_B: float | None = Input(None, "Pa", "Factor B from the II-D material chart (blank = elastic)", gt=0)
    factor_A: float | None = Input(None, "", "Factor A from Fig. G (blank = estimated)", gt=0)
    S: float | None = Input(None, "Pa", "Allowable stress (only for Do/t < 10)", gt=0)


@register_tool("asme.external_pressure", "External pressure, cylinder (UG-28)", ExternalPressureInputs,
               description="Allowable external pressure of a cylinder from factor A (estimated or from Fig. G) "
                           "and a user-supplied factor B; Section II-D charts are not reproduced.",
               reference="ASME VIII-1 UG-28(c); factor A from the elastic buckling strain (Windenburg & Trilling, "
                         "1934; long-cylinder limit A = 1.1/(Do/t)²), validated by hand calculation." + REF_NOTE,
               tags=TAGS + ("vacuum", "buckling"), charts=_charts.external_charts)
def external_pressure_tool(inp: ExternalPressureInputs) -> ExternalPressureResult:
    E = inp.E_modulus or _modulus(inp.material, inp.T)
    return external_pressure_cylinder(inp.P_external, inp.Do, inp.L, inp.t_nominal, E, inp.factor_B, inp.factor_A,
                                      inp.corrosion, inp.S)


# ---------------- hydrostatic test ----------------

class HydrotestInputs(BaseModel):
    mawp: float = Input(1.0e6, "Pa", "MAWP (or design pressure)", gt=0)
    S_test: float = Input(138e6, "Pa", "Allowable stress at test temperature", S_HELP, gt=0)
    S_design: float = Input(138e6, "Pa", "Allowable stress at design temperature", S_HELP, gt=0)


@register_tool("asme.hydrotest", "Hydrostatic test pressure (UG-99)", HydrotestInputs,
               description="Minimum hydrostatic test pressure 1.3 × MAWP × stress ratio (UG-99(b)).",
               reference="ASME VIII-1 UG-99(b); validated by hand calculation." + REF_NOTE, tags=TAGS)
def hydrotest_tool(inp: HydrotestInputs) -> HydrotestResult:
    return hydrotest_pressure(inp.mawp, inp.S_test, inp.S_design)


# ---------------- vessel builder ----------------

class DesignConditions(BaseModel):
    P: float = Input(1.0e6, "Pa", "Internal design pressure", gt=0)
    T: float = Input(423.15, "K", "Design temperature")
    P_external: float = Input(0.0, "Pa", "External design pressure (0 = none, vacuum = 101.3 kPa)", ge=0)


class VesselMaterial(BaseModel):
    material: str = Input("Steel", "", "Material (modulus and density)", json_schema_extra={"choices": "materials:metal"})
    S: float = Input(138e6, "Pa", "Allowable stress S at design temperature", S_HELP, gt=0)
    S_test: float | None = Input(None, "Pa", "Allowable stress at test temperature (blank = S)", gt=0)
    corrosion: float = Input(3e-3, "m", "Corrosion allowance", ge=0)
    undertolerance: float = Input(0.0, "m", "Mill undertolerance", ge=0)


class VesselShell(BaseModel):
    kind: Literal["cylinder", "sphere"] = Input("cylinder", "", "Shell type")
    D_inside: float = Input(1.2, "m", "Inside diameter (new)", gt=0)
    length: float = Input(3.0, "m", "Tangent-to-tangent length (cylinder)", gt=0)
    E: JointE = Input(0.85, "", "Longitudinal joint efficiency E", E_HELP)
    E_circ: JointE | None = Input(None, "", "Circumferential joint efficiency (blank = E)", E_HELP)
    t_nominal: float | None = Input(None, "m", "Nominal thickness (blank = next standard plate)", gt=0)


class VesselHeads(BaseModel):
    kind: HeadKindInput = Input("ellipsoidal_2_1", "", "Head type (both ends)")
    E: JointE = Input(1.0, "", "Head joint efficiency (1.0 = seamless)", E_HELP)
    t_nominal: float | None = Input(None, "m", "Nominal thickness (blank = next standard plate)", gt=0)
    ratio: float = Input(2.0, "", "Ellipsoidal D/2h (general ellipsoidal)", ge=1.0, le=3.0)
    crown_radius: float | None = Input(None, "m", "Torispherical crown radius L (blank = D)", gt=0)
    knuckle_radius: float | None = Input(None, "m", "Torispherical knuckle radius r (blank = 0.06 L)", gt=0)
    flat_C: FlatC = Input(0.33, "", "Flat head attachment factor C", C_HELP)


class VesselNozzle(BaseModel):
    name: str = Input("N1", "", "Tag")
    location: Literal["shell", "head"] = Input("shell", "", "Location")
    d: float = Input(0.1541, "m", "Inside diameter (new)", gt=0)
    t: float = Input(7.11e-3, "m", "Nominal wall", gt=0)
    S: float | None = Input(None, "Pa", "Nozzle allowable stress (blank = vessel S)", gt=0)
    pad_diameter: float = Input(0.3, "m", "Pad outside diameter (0 = no pad)", ge=0)
    pad_thickness: float = Input(10e-3, "m", "Pad thickness", ge=0)
    weld_leg: float = Input(6e-3, "m", "Nozzle fillet weld leg", ge=0)
    pad_weld_leg: float = Input(6e-3, "m", "Pad fillet weld leg", ge=0)
    inward_projection: float = Input(0.0, "m", "Inward projection", ge=0)


class VesselExternal(BaseModel):
    L: float | None = Input(None, "m", "Design length L (blank = T-T + 1/3 of each head depth)", gt=0)
    factor_B: float | None = Input(None, "Pa", "Factor B from the II-D chart (blank = elastic)", gt=0)
    factor_A: float | None = Input(None, "", "Factor A from Fig. G (blank = estimated)", gt=0)


class VesselDesignInputs(BaseModel):
    conditions: DesignConditions = Field(default_factory=DesignConditions, description="Design conditions")
    material: VesselMaterial = Field(default_factory=VesselMaterial, description="Material, S, CA")
    shell: VesselShell = Field(default_factory=VesselShell, description="Shell")
    heads: VesselHeads = Field(default_factory=VesselHeads, description="Heads")
    nozzles: list[VesselNozzle] = Field(default_factory=lambda: [VesselNozzle()], description="Nozzles")
    external: VesselExternal = Field(default_factory=VesselExternal, description="External pressure")


@register_tool("asme.vessel_design", "Pressure vessel builder (VIII-1)", VesselDesignInputs,
               description="Step-by-step vessel sizing: UG-27 shell, UG-32/UG-34 heads, UG-37 nozzles, UG-28 "
                           "external pressure and the UG-99(b) hydrotest, with a pass/fail summary.",
               reference="ASME VIII-1 UG-16, UG-27, UG-28, UG-32, UG-34, UG-37, UG-99; each part validated by "
                         "hand calculation (see the individual tools)." + REF_NOTE,
               tags=TAGS, custom_page=True, charts=_charts.vessel_charts)
def vessel_design_tool(inp: VesselDesignInputs) -> VesselDesignResult:
    c, m, sh, hd, ex = inp.conditions, inp.material, inp.shell, inp.heads, inp.external
    mat = get_material(m.material)
    nozzles = [Nozzle(n.name, n.d, n.t, n.location, n.S, n.pad_diameter, n.pad_thickness, n.weld_leg,
                      n.pad_weld_leg, n.inward_projection) for n in inp.nozzles]
    return vessel_design(
        c.P, sh.D_inside, m.S, sh.length, sh.kind, sh.E, sh.E_circ, m.corrosion, m.undertolerance, sh.t_nominal,
        hd.kind, hd.E, hd.t_nominal, hd.ratio, hd.crown_radius, hd.knuckle_radius, hd.flat_C, nozzles,
        c.P_external, _modulus(m.material, c.T), ex.factor_B, ex.factor_A, ex.L, m.S_test, mat.prop("rho"),
    )
