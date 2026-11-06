"""Chart specs for the structural tools (SI units; front ends convert for display)."""
from __future__ import annotations

import numpy as np

from engtoolkit.core.charts import Chart, Series, Shape

PRIMARY, ACCENT, ORANGE, BLUE = "#E0A800", "#2A9D8F", "#C8632B", "#3D7EA6"


def section_charts(section, res=None) -> list[Chart]:
    outline = section.outline()
    shapes = [Shape(outline["outer"])] + [Shape(h, hole=True) for h in outline["holes"]]
    return [Chart("section", "Cross-section", "z", "m", "y", "m", equal_aspect=True, shapes=shapes, series=[
        Series("Centroid", [section.CoG_z], [section.CoG_y], mode="markers", color="#0F172A"),
        Series("Shear centre", [section.CoS_z], [section.CoS_y], mode="markers", color=ORANGE),
    ])]


def beam_charts(inp, res, section=None) -> list[Chart]:
    charts = [
        Chart("deflection", "Deflection", "x", "m", "Deflection", "m",
              series=[Series("Deflection", res.x, res.deflection, color=PRIMARY)]),
        Chart("slope", "Slope", "x", "m", "Slope", "rad",
              series=[Series("Slope", res.x, res.slope, color=ACCENT)]),
        Chart("shear", "Shear force", "x", "m", "Shear", "N",
              series=[Series("Shear", res.x_internal, res.shear, fill=True, color=BLUE)]),
        Chart("moment", "Bending moment (sagging +)", "x", "m", "Moment", "N·m",
              series=[Series("Moment", res.x_internal, res.moment, fill=True, color=ORANGE)]),
    ]
    if section is not None:
        charts.append(section_charts(section)[0])
        charts.append(_bending_stress_chart(section, res))
    return charts


def _bending_stress_chart(section, res) -> Chart:
    """Linear bending stress over the depth at the section of maximum |M| (strong axis, tension +)."""
    x0 = res.x_max_moment
    M = float(np.interp(x0, res.x_internal, res.moment))
    y = [-section.c_bottom, section.c_top]
    sigma = [-M * v / section.Iyy for v in y]
    return Chart("bending_stress", f"Bending stress across the section at x = {x0:.3g} m (tension +)",
                 "Stress", "Pa", "y", "m", series=[
                     Series("Bending stress", sigma, y, fill=True, color=ORANGE),
                     Series("Neutral axis", [0.0, 0.0], y, dash=True, color=BLUE),
                 ])


def torsion_charts(res, section=None) -> list[Chart]:
    """Twist (and Saint-Venant-only twist), torque split, bimoment (restrained warping) and the section.

    ``section``: a CrossSection, or for a drawn section {"nodes": [(x2, x3)], "walls": [(i, j)], "SC": (x2, x3)}.
    """
    restrained = res.mode == "restrained" and res.C_T > 0
    twist = [Series("Twist ϑ", res.x, res.theta, color=PRIMARY)]
    if restrained:
        twist[0].name = "With warping restraint"
        twist.append(Series("Saint-Venant only", res.x, res.theta_sv, dash=True, color=ACCENT))
    charts = [
        Chart("twist", "Twist along the member", "x", "m", "Twist", "rad", series=twist),
        Chart("torque", "Torque split T = M_SV + M_B", "x", "m", "Torque", "N·m", series=[
            Series("T total", res.x, res.T_total, color="#0F172A"),
            Series("M_SV (Saint-Venant)", res.x, res.M_sv, fill=True, color=BLUE),
            Series("M_B (warping)", res.x, res.M_b, fill=True, color=ORANGE),
        ]),
    ]
    if restrained:
        charts.append(Chart("bimoment", "Bimoment B = −E C_T ϑ''", "x", "m", "B", "N·m^2",
                            series=[Series("Bimoment", res.x, res.bimoment, fill=True, color=ORANGE)]))
    if isinstance(section, dict):
        P = section["nodes"]
        series = [Series(f"Wall {k}", [P[i][0], P[j][0]], [-P[i][1], -P[j][1]], color=PRIMARY)
                  for k, (i, j) in enumerate(section["walls"])]
        series.append(Series("Shear centre", [section["SC"][0]], [-section["SC"][1]], mode="markers", color=ORANGE))
        charts.append(Chart("section", "Cross-section (mid-lines)", "x2", "m", "−x3 (up)", "m", equal_aspect=True,
                            series=series))
    elif section is not None:
        charts.append(section_charts(section)[0])
    return charts
