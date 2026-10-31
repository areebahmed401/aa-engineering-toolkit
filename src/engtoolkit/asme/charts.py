"""Chart specs for the ASME tools (SI units; front ends convert for display)."""
from __future__ import annotations

import math

import numpy as np

from engtoolkit.core.charts import Chart, Series, Shape

from .div1.external_pressure import factor_A
from .div1.heads import flat_head, formed_head, head_depth
from .div1.nozzles import nozzle_reinforcement
from .div1.shells import cylinder_circumferential_t, cylinder_longitudinal_t, sphere_t

PRIMARY, ACCENT, ORANGE, BLUE, GREY = "#4F46E5", "#06B6D4", "#F97316", "#0EA5E9", "#64748B"
HEAD_LABELS = {"ellipsoidal_2_1": "2:1 ellipsoidal", "ellipsoidal": "Ellipsoidal", "torispherical": "Torispherical",
               "hemispherical": "Hemispherical", "flat": "Flat"}


def _pressures(P: float) -> np.ndarray:
    return np.linspace(0.05 * P, 2 * P, 40)


def _marker(name, x, y, color="#0F172A"):
    return Series(name, [x], [y], mode="markers", color=color)


def shell_charts(inp, res) -> list[Chart]:
    P = inp.P
    ps = _pressures(P)
    R = inp.D_inside / 2 + inp.corrosion
    ca = inp.corrosion + inp.undertolerance
    if res.governing == "membrane stress":  # sphere
        series = [Series("Sphere UG-27(d)", ps, [sphere_t(p, R, inp.S, inp.E)[0] + ca for p in ps], color=PRIMARY)]
    else:
        Ec = inp.E_circ or inp.E
        series = [
            Series("Circumferential stress", ps, [cylinder_circumferential_t(p, R, inp.S, inp.E)[0] + ca for p in ps],
                   color=PRIMARY),
            Series("Longitudinal stress", ps, [cylinder_longitudinal_t(p, R, inp.S, Ec)[0] + ca for p in ps],
                   color=ACCENT),
        ]
    series += [Series("Nominal plate", [ps[0], ps[-1]], [res.t_nominal] * 2, dash=True, color=GREY),
               _marker("Design point", P, res.t_required)]
    return [Chart("t_vs_P", "Required thickness (incl. CA) vs design pressure", "Design pressure", "Pa",
                  "Thickness", "m", series=series)]


def head_charts(inp, res) -> list[Chart]:
    P = inp.P
    ps = _pressures(P)
    series = []
    for kind, color in (("ellipsoidal_2_1", PRIMARY), ("torispherical", ORANGE), ("hemispherical", ACCENT)):
        t = [formed_head(p, inp.D_inside, inp.S, kind, inp.E, inp.corrosion, ug16_min=0).t_required for p in ps]
        series.append(Series(HEAD_LABELS[kind] + (" (selected)" if kind == inp.kind else ""), ps, t, color=color,
                             dash=kind != inp.kind))
    if inp.kind == "ellipsoidal":
        t = [formed_head(p, inp.D_inside, inp.S, "ellipsoidal", inp.E, inp.corrosion, ratio=inp.ratio,
                         ug16_min=0).t_required for p in ps]
        series.append(Series(f"Ellipsoidal D/2h = {inp.ratio:g} (selected)", ps, t, color=BLUE))
    series.append(_marker("Design point", P, res.t_required))
    return [Chart("t_vs_P", "Head thickness (incl. CA) vs design pressure", "Design pressure", "Pa",
                  "Thickness", "m", series=series)]


def flat_head_charts(inp, res) -> list[Chart]:
    ps = _pressures(inp.P)
    series = []
    for C, color in zip((0.17, 0.20, 0.33), (ACCENT, BLUE, PRIMARY)):
        t = [flat_head(p, inp.d, inp.S, C, inp.E, inp.corrosion, W=inp.W, h_G=inp.h_G, ug16_min=0).t_required
             for p in ps]
        series.append(Series(f"C = {C:g}", ps, t, color=color, dash=abs(C - inp.C) > 1e-9))
    series.append(_marker("Design point", inp.P, res.t_required))
    return [Chart("t_vs_P", "Flat head thickness (incl. CA) vs design pressure", "Design pressure", "Pa",
                  "Thickness", "m", series=series)]


def nozzle_charts(inp, res) -> list[Chart]:
    te = np.linspace(0, max(2.0 * inp.t_host, inp.pad_thickness * 1.5, 1e-3), 30)
    Dp = inp.pad_diameter if inp.pad_diameter > 0 else 2 * inp.d_nozzle
    req, avail = [], []
    for t in te:
        r = nozzle_reinforcement(inp.P, inp.host, inp.D_host, inp.t_host, inp.S_host, inp.d_nozzle, inp.t_nozzle,
                                 inp.S_nozzle, inp.corrosion, pad_diameter=Dp if t > 0 else 0.0, pad_thickness=t,
                                 weld_leg_nozzle=inp.weld_leg_nozzle, weld_leg_pad=inp.weld_leg_pad,
                                 inward_projection=inp.inward_projection, crown_radius=inp.crown_radius)
        req.append(r.A_required)
        avail.append(r.A_available)
    return [Chart("area_vs_pad", f"Reinforcement area vs pad thickness (pad Ø {Dp * 1e3:.0f} mm)",
                  "Pad thickness", "m", "Area", "m^2", series=[
                      Series("Required A", te, req, color=ORANGE, dash=True),
                      Series("Available", te, avail, color=PRIMARY),
                      _marker("Current design", inp.pad_thickness, res.A_available),
                  ])]


def external_charts(inp, res) -> list[Chart]:
    E = res.P_elastic * 3 * res.Do_over_t / (2 * res.A) if res.A > 0 else math.nan
    t_max = max(inp.t_nominal * 2.5, 1e-3)
    ts = np.linspace(t_max / 40, t_max, 40)
    pa = [2 * factor_A(inp.L, inp.Do, t) * E / (3 * inp.Do / t) for t in ts]
    series = [Series("Elastic Pa (estimated A)", ts + inp.corrosion, pa, color=PRIMARY),
              Series("External design pressure", [ts[0], ts[-1] + inp.corrosion], [inp.P_external] * 2, dash=True,
                     color=ORANGE),
              _marker("Current design", inp.t_nominal, res.P_allowable)]
    LDs = np.geomspace(0.05, 50, 60)
    t = res.t
    A_curve = [factor_A(ld * inp.Do, inp.Do, t) for ld in LDs]
    return [
        Chart("pa_vs_t", "Allowable external pressure vs nominal thickness (elastic region)", "Nominal thickness",
              "m", "Pa", "Pa", series=series),
        Chart("A_vs_L", f"Estimated factor A vs L/Do at Do/t = {res.Do_over_t:.0f} (not Fig. G)", "L/Do", "",
              "Factor A", "", log_x=True, log_y=True, series=[
                  Series("A (elastic buckling estimate)", LDs, A_curve, color=PRIMARY),
                  _marker("Design", res.L_over_Do, res.A)]),
    ]


def _head_profile(kind, D, h_ratio, L, r, n=40):
    """Inside head profile (radius, height above tangent) from shell wall to crown."""
    R = D / 2
    if kind == "flat":
        return [(R, 0.0), (0.0, 0.0)]
    if kind in ("ellipsoidal_2_1", "ellipsoidal", "hemispherical"):
        h = head_depth(kind, D, h_ratio)
        th = np.linspace(0, math.pi / 2, n)
        return list(zip(R * np.cos(th), h * np.sin(th)))
    L = D if L is None else L
    r = 0.06 * L if r is None else r
    h = head_depth("torispherical", D, L=L, r=r)
    # knuckle centre (R - r, 0); crown centre (0, h - L)
    phi = math.asin((R - r) / (L - r))  # crown half-angle at the knuckle tangency point
    th = np.linspace(0, math.pi / 2 - phi, n // 2)
    knuckle = [(R - r + r * math.cos(a), r * math.sin(a)) for a in th]
    a2 = np.linspace(phi, 0, n // 2)
    crown = [(L * math.sin(a), h - L + L * math.cos(a)) for a in a2]
    return knuckle + crown


def vessel_outline(inp, res) -> Chart:
    """Half-section of the vessel (axis vertical) with nominal walls, for display."""
    sh, hd = inp.shell, inp.heads
    D = sh.D_inside
    if sh.kind == "sphere":
        t = res.shell_t_nominal
        th = np.linspace(-math.pi / 2, math.pi / 2, 60)
        outer = [(0.0, -(D / 2 + t))] + [((D / 2 + t) * math.cos(a), (D / 2 + t) * math.sin(a)) for a in th] + \
            [(0.0, D / 2 + t)]
        inner = [(0.0, -D / 2)] + [(D / 2 * math.cos(a), D / 2 * math.sin(a)) for a in th] + [(0.0, D / 2)]
        return Chart("outline", "Vessel half-section", "Radius", "m", "Height", "m", equal_aspect=True,
                     shapes=[Shape(outer + [(0.0, 0.0)]), Shape(inner, hole=True)])
    Lt = sh.length
    ts, th_ = res.shell_t_nominal, res.head_t_nominal
    prof_in = _head_profile(hd.kind, D, hd.ratio, hd.crown_radius, hd.knuckle_radius)
    # outer surface: inside profile scaled out by the head thickness (display only)
    h_in = prof_in[-1][1] if hd.kind != "flat" else 0.0
    sx = (D / 2 + th_) / (D / 2)
    prof_out = [(x * sx, y * (h_in + th_) / h_in if h_in > 0 else y + th_) for x, y in prof_in]

    def body(profile, wall):
        top = [(x, Lt + y) for x, y in profile]
        bottom = [(x, -y) for x, y in reversed(profile)]
        R = D / 2 + wall
        return [(0.0, bottom[0][1])] + bottom + [(R, 0.0), (R, Lt)] + top

    outer = body(prof_out, ts)
    inner = body(prof_in, 0.0)
    nozzle_series = []
    for nz in inp.nozzles:
        if nz.location == "shell":
            y = Lt / 2
            x0 = D / 2
            nozzle_series.append(Series(f"Nozzle {nz.name}", [x0, x0 + 0.15 * D + ts], [y, y], color=ORANGE))
        else:
            ytop = Lt + prof_out[-1][1]
            nozzle_series.append(Series(f"Nozzle {nz.name}", [D / 6, D / 6], [ytop - th_, ytop + 0.12 * D],
                                        color=ORANGE))
    return Chart("outline", "Vessel half-section (nominal walls, not to scale for nozzles)", "Radius", "m",
                 "Height above bottom tangent line", "m", equal_aspect=True,
                 shapes=[Shape(outer), Shape(inner, hole=True)], series=nozzle_series)


def vessel_charts(inp, res) -> list[Chart]:
    charts = [vessel_outline(inp, res)]
    m, sh, hd = inp.material, inp.shell, inp.heads
    P = inp.conditions.P
    ps = _pressures(P)
    R = sh.D_inside / 2 + m.corrosion
    ca = m.corrosion + m.undertolerance
    if sh.kind == "sphere":
        series = [Series("Sphere", ps, [sphere_t(p, R, m.S, sh.E)[0] + ca for p in ps], color=PRIMARY)]
    else:
        series = [Series("Shell", ps, [max(cylinder_circumferential_t(p, R, m.S, sh.E)[0],
                                           cylinder_longitudinal_t(p, R, m.S, sh.E_circ or sh.E)[0]) + ca
                                       for p in ps], color=PRIMARY)]
        if hd.kind == "flat":
            ht = [flat_head(p, sh.D_inside, m.S, hd.flat_C, hd.E, m.corrosion, ug16_min=0).t_required for p in ps]
        else:
            ht = [formed_head(p, sh.D_inside, m.S, hd.kind, hd.E, m.corrosion, None, hd.ratio, hd.crown_radius,
                              hd.knuckle_radius, m.undertolerance, ug16_min=0).t_required for p in ps]
        series.append(Series(f"Heads ({HEAD_LABELS[hd.kind]})", ps, ht, color=ORANGE))
    series.append(_marker("Design pressure", P, res.shell_t_required))
    charts.append(Chart("t_vs_P", "Required thickness (incl. CA) vs design pressure", "Design pressure", "Pa",
                        "Thickness", "m", series=series))
    return charts
