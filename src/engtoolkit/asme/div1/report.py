"""
Vessel summary: a cylindrical (or spherical) vessel with two identical heads and any number of
nozzles, checked for internal pressure, optional external pressure and the hydrostatic test.

    from engtoolkit.asme.div1 import Nozzle, vessel_design
    r = vessel_design(P=1.0e6, D_inside=1.2, length=3.0, S=138e6, E=0.85, corrosion=3e-3,
                      head_kind="ellipsoidal_2_1", nozzles=[Nozzle("N1", d=0.154, t=7.1e-3)])
    print(r.to_markdown())

Preliminary sizing only: verify against the current edition of ASME BPVC VIII-1. S is a user input
(Section II-D); no code tables are reproduced.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from engtoolkit.core.results import Result, rfield

from .common import DISCLAIMER, HydrotestResult, hydrotest_pressure
from .external_pressure import ExternalPressureResult, external_pressure_cylinder
from .heads import HeadKind, HeadResult, flat_head, formed_head, head_depth
from .nozzles import NozzleResult, nozzle_reinforcement
from .shells import ShellResult, cylindrical_shell, spherical_shell

ShellKind = Literal["cylinder", "sphere"]

# approximate inside surface area / D² and volume / D³ of one head (for mass and capacity estimates)
_HEAD_AREA = {"ellipsoidal_2_1": 1.084, "hemispherical": math.pi / 2, "torispherical": 0.931, "flat": math.pi / 4}
_HEAD_VOLUME = {"ellipsoidal_2_1": math.pi / 24, "hemispherical": math.pi / 12, "torispherical": 0.0809, "flat": 0.0}


@dataclass
class Nozzle:
    """A set-in nozzle (dimensions new, in m). ``location`` is "shell" or "head"."""
    name: str = "N1"
    d: float = 0.154                 # inside diameter
    t: float = 7.1e-3                # nominal wall
    location: Literal["shell", "head"] = "shell"
    S: float | None = None           # allowable stress of the nozzle material (default: vessel S)
    pad_diameter: float = 0.0
    pad_thickness: float = 0.0
    weld_leg: float = 0.0
    pad_weld_leg: float = 0.0
    inward_projection: float = 0.0


@dataclass
class VesselDesignResult(Result):
    status: str = rfield("", "Overall status")
    mawp: float = rfield("Pa", "Vessel MAWP (corroded, governing part)")
    mawp_governed_by: str = rfield("", "MAWP governed by")
    design_pressure: float = rfield("Pa", "Design pressure")
    hydro_test_pressure: float = rfield("Pa", "Hydrostatic test pressure (UG-99(b))")
    shell_t_required: float = rfield("m", "Shell required t incl. CA")
    shell_t_nominal: float = rfield("m", "Shell nominal t")
    head_t_required: float = rfield("m", "Head required t incl. CA")
    head_t_nominal: float = rfield("m", "Head nominal t")
    external_allowable: float = rfield("Pa", "Allowable external pressure", default=math.nan)
    nozzles_passing: str = rfield("", "Nozzles passing", default="")
    volume: float = rfield("m³", "Internal volume (approx.)", default=math.nan)
    mass_empty: float = rfield("kg", "Empty mass, shell + heads (approx.)", default=math.nan)
    checks: list = rfield("", "Checks", default_factory=list, summary=False)
    shell: ShellResult | None = rfield("", "Shell", default=None, summary=False)
    head: HeadResult | None = rfield("", "Heads", default=None, summary=False)
    nozzles: list = rfield("", "Nozzles", default_factory=list, summary=False)
    external: ExternalPressureResult | None = rfield("", "External pressure", default=None, summary=False)
    hydrotest: HydrotestResult | None = rfield("", "Hydrotest", default=None, summary=False)
    parts: list = rfield("", "Part results with labels and units (for front ends)", default_factory=list,
                         summary=False)
    notes: list = rfield("", "Notes", default_factory=list, summary=False)
    disclaimer: str = rfield("", "Disclaimer", default=DISCLAIMER, summary=False)

    def to_markdown(self, title: str = "Pressure vessel: ASME VIII-1 preliminary sizing") -> str:
        """Markdown report in mm and MPa (also used by the notebook)."""
        def fmt(v, unit):
            if v is None or (isinstance(v, float) and not math.isfinite(v)):
                return "–"
            if unit == "m":
                return f"{v * 1e3:.2f} mm"
            if unit == "Pa":
                return f"{v / 1e6:.4g} MPa"
            if unit == "m^2":
                return f"{v * 1e6:.0f} mm²"
            if unit in ("m³", "kg"):
                return f"{v:.4g} {unit}"
            return f"{v:.4g}" if isinstance(v, float) else str(v)

        lines = [f"# {title}", "", f"**Overall status: {self.status}**", "",
                 "| Result | Value |", "|---|---|"]
        for item in self.fields_info():
            if item["summary"] and not isinstance(item["value"], (list, dict)):
                lines.append(f"| {item['label']} | {fmt(item['value'], item['unit'])} |")
        lines += ["", "## Checks", "", "| Item | Clause | Required | Provided | Status |", "|---|---|---|---|---|"]
        for c in self.checks:
            lines.append(f"| {c['item']} | {c['clause']} | {fmt(c['required'], c['unit'])} | "
                         f"{fmt(c['provided'], c['unit'])} | {c['status']} |")
        if self.notes:
            lines += ["", "## Notes", ""] + [f"- {n}" for n in self.notes]
        lines += ["", f"> {self.disclaimer}", ""]
        return "\n".join(lines)


def _check(item, clause, required, provided, unit, status=None):
    ok = provided >= required * (1 - 1e-9) if status is None else status == "PASS"
    return {"item": item, "clause": clause, "required": required, "provided": provided, "unit": unit,
            "status": "PASS" if ok else "FAIL"}


def vessel_design(P: float, D_inside: float, S: float, length: float = 3.0, shell_kind: ShellKind = "cylinder",
                  E: float = 1.0, E_circ: float | None = None, corrosion: float = 0.0, undertolerance: float = 0.0,
                  shell_t_nominal: float | None = None, head_kind: HeadKind = "ellipsoidal_2_1",
                  head_E: float = 1.0, head_t_nominal: float | None = None, head_ratio: float = 2.0,
                  crown_radius: float | None = None, knuckle_radius: float | None = None,
                  flat_C: float = 0.33, nozzles: list[Nozzle] | None = None, P_external: float = 0.0,
                  E_modulus: float = 200e9, factor_B: float | None = None, factor_A: float | None = None,
                  L_external: float | None = None, S_test: float | None = None, density: float = 7850.0
                  ) -> VesselDesignResult:
    """
    Size a vessel: UG-27 shell, UG-32/UG-34 heads (two identical heads; none for a sphere), UG-37
    nozzles, optional UG-28 external pressure on the cylinder and the UG-99(b) hydrotest pressure.

    ``length`` is the tangent-to-tangent length of the cylinder, ``S`` the allowable stress at design
    temperature and ``S_test`` at test temperature (default S). Nominal thicknesses left as None are
    rounded up to the next standard plate.
    """
    nozzles = list(nozzles or [])
    notes: list[str] = []
    checks: list[dict] = []

    if shell_kind == "sphere":
        shell = spherical_shell(P, D_inside, S, E, corrosion, shell_t_nominal, undertolerance)
        head = None
    else:
        shell = cylindrical_shell(P, D_inside, S, E, corrosion, shell_t_nominal, E_circ, undertolerance)
        if head_kind == "flat":
            head = flat_head(P, D_inside, S, flat_C, head_E, corrosion, head_t_nominal, undertolerance=undertolerance)
        else:
            head = formed_head(P, D_inside, S, head_kind, head_E, corrosion, head_t_nominal, head_ratio,
                               crown_radius, knuckle_radius, undertolerance)
    checks.append(_check("Shell thickness", shell.clause, shell.t_required, shell.t_nominal, "m"))
    checks.append(_check("Shell MAWP ≥ design pressure", shell.clause, P, shell.mawp, "Pa"))
    parts = {"shell": shell.mawp}
    if head is not None:
        checks.append(_check("Head thickness", head.clause, head.t_required, head.t_nominal, "m"))
        checks.append(_check("Head MAWP ≥ design pressure", head.clause, P, head.mawp, "Pa"))
        parts["heads"] = head.mawp
        notes += [f"Head: {n}" for n in head.notes]
    notes += [f"Shell: {n}" for n in shell.notes]

    noz_results: list[NozzleResult] = []
    noz_names: list[str] = []
    host_kind = "sphere" if shell_kind == "sphere" else "cylinder"
    for nz in nozzles:
        on_head = nz.location == "head" and head is not None
        if on_head and head_kind == "flat":
            notes.append(f"{nz.name}: openings in flat heads (UG-39) are not checked")
            continue
        host = head_kind if on_head else host_kind
        if host == "ellipsoidal":
            host = "ellipsoidal_2_1"
            notes.append(f"{nz.name}: general ellipsoidal head checked with the 2:1 K1 = 0.9 sphere radius")
        t_host = head.t_nominal if on_head else shell.t_nominal
        r = nozzle_reinforcement(P, host, D_inside, t_host, S, nz.d, nz.t, nz.S, corrosion,
                                 pad_diameter=nz.pad_diameter, pad_thickness=nz.pad_thickness,
                                 weld_leg_nozzle=nz.weld_leg, weld_leg_pad=nz.pad_weld_leg,
                                 inward_projection=nz.inward_projection, crown_radius=crown_radius)
        noz_results.append(r)
        noz_names.append(nz.name)
        checks.append(_check(f"Nozzle {nz.name} reinforcement ({nz.location})", r.clause, r.A_required,
                             r.A_available, "m^2", r.status))

    external = None
    if P_external > 0:
        if shell_kind == "sphere":
            notes.append("External pressure on spheres (UG-28(d)) is not checked")
        else:
            depth = head_depth(head_kind, D_inside, head_ratio, crown_radius, knuckle_radius) if head else 0.0
            L = L_external if L_external is not None else length + 2 * depth / 3
            Do = D_inside + 2 * shell.t_nominal
            external = external_pressure_cylinder(P_external, Do, L, shell.t_nominal, E_modulus, factor_B,
                                                  factor_A, corrosion, S)
            checks.append(_check("Shell external pressure", "UG-28(c)", P_external, external.P_allowable, "Pa"))
            notes += [f"External: {n}" for n in external.notes]
            notes.append("Heads under external pressure (UG-33) are not checked")

    governing = min(parts, key=parts.get)
    mawp = parts[governing]
    hydro = hydrotest_pressure(mawp, S if S_test is None else S_test, S)

    # capacity and mass estimates
    Dm_shell = D_inside + shell.t_nominal
    if shell_kind == "sphere":
        volume = math.pi * D_inside ** 3 / 6
        mass = math.pi * Dm_shell ** 2 * shell.t_nominal * density
    else:
        hk = head_kind if head_kind in _HEAD_VOLUME else "ellipsoidal_2_1"
        volume = math.pi * D_inside ** 2 / 4 * length + 2 * _HEAD_VOLUME[hk] * D_inside ** 3
        mass = (math.pi * Dm_shell * shell.t_nominal * length
                + 2 * _HEAD_AREA[hk] * (D_inside + head.t_nominal) ** 2 * head.t_nominal) * density
    n_ok = sum(r.status == "PASS" for r in noz_results)
    status = "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL"
    notes.append("Supports, nozzle loads, wind/seismic, UG-45 neck thickness and flange ratings are not checked")
    parts = [{"name": "Shell", "fields": shell.fields_info()}]
    if head is not None:
        parts.append({"name": "Heads", "fields": head.fields_info()})
    parts += [{"name": f"Nozzle {name}", "fields": r.fields_info()} for name, r in zip(noz_names, noz_results)]
    if external is not None:
        parts.append({"name": "External pressure", "fields": external.fields_info()})
    parts.append({"name": "Hydrostatic test", "fields": hydro.fields_info()})
    return VesselDesignResult(
        status=status, mawp=mawp, mawp_governed_by=governing, design_pressure=P,
        hydro_test_pressure=hydro.test_pressure,
        shell_t_required=shell.t_required, shell_t_nominal=shell.t_nominal,
        head_t_required=head.t_required if head else math.nan, head_t_nominal=head.t_nominal if head else math.nan,
        external_allowable=external.P_allowable if external else math.nan,
        nozzles_passing=f"{n_ok}/{len(noz_results)}", volume=volume, mass_empty=mass,
        checks=checks, shell=shell, head=head, nozzles=noz_results, external=external, hydrotest=hydro,
        parts=parts, notes=notes,
    )
