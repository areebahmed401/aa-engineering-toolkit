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


def torsion_charts(beam, torque, res) -> list[Chart]:
    from .torsion import Torsion, saint_venant_twist
    x = np.linspace(0, beam.length, 51)
    sv = [saint_venant_twist(torque, xi, beam.material.G, beam.shape.J_torsion) for xi in x]
    series = [Series("Saint-Venant only", x, sv, dash=True, color=ACCENT)]
    if beam.shape.C_torsion > 0:
        t = Torsion(beam, torque, beam.length)
        series.insert(0, Series("With warping restraint", x, [t.theta(xi / beam.length) for xi in x], color=PRIMARY))
    return [Chart("twist", "Twist along the cantilever", "x", "m", "Twist", "rad", series=series),
            section_charts(beam.shape)[0]]
