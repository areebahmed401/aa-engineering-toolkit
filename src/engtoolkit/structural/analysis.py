"""
One-call beam analysis: checks static determinacy, picks equilibrium or FEM, and returns
reactions, diagrams and peak stresses.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from engtoolkit.core.results import Result, rfield

from .determinate import DeterminateSolver
from .fem import FEMSolver
from .loads import static_determinacy


@dataclass
class BeamAnalysisResult(Result):
    verdict: str = rfield("", "Determinacy")
    method: str = rfield("", "Method used")
    degree_of_indeterminacy: int = rfield("", "Degree of indeterminacy")
    Ay: float = rfield("N", "Left vertical reaction", default=math.nan)
    MA: float = rfield("N·m", "Left moment reaction", default=math.nan)
    By: float = rfield("N", "Right vertical reaction", default=math.nan)
    MB: float = rfield("N·m", "Right moment reaction", default=math.nan)
    max_deflection: float = rfield("m", "Max |deflection|", default=math.nan)
    max_moment: float = rfield("N·m", "Max |bending moment|", default=math.nan)
    max_shear: float = rfield("N", "Max |shear force|", default=math.nan)
    max_bending_stress: float = rfield("Pa", "Max bending stress", default=math.nan)
    utilisation: float = rfield("", "Bending stress / yield", default=math.nan)
    x_max_deflection: float = rfield("m", "Position of max |deflection|", default=math.nan)
    x_max_moment: float = rfield("m", "Position of max |moment| (max bending stress)", default=math.nan)
    x_max_shear: float = rfield("m", "Position of max |shear|", default=math.nan)
    yield_strength: float = rfield("Pa", "Yield strength", default=math.nan)
    section: str = rfield("", "Section", default="")
    c_top: float = rfield("m", "Centroid to top fibre", default=math.nan)
    c_bottom: float = rfield("m", "Centroid to bottom fibre", default=math.nan)
    x: list = rfield("m", "x (deflection)", default_factory=list, summary=False)
    deflection: list = rfield("m", "Deflection", default_factory=list, summary=False)
    slope: list = rfield("rad", "Slope", default_factory=list, summary=False)
    x_internal: list = rfield("m", "x (internal forces)", default_factory=list, summary=False)
    shear: list = rfield("N", "Shear force", default_factory=list, summary=False)
    moment: list = rfield("N·m", "Bending moment", default_factory=list, summary=False)
    # Strong-axis (Iyy) bending only, tension positive; sagging M > 0 compresses the top fibre.
    # Unsymmetric sections (Z, L) also have Iyz and would bend about a tilted axis: not captured here.
    sigma_top: list = rfield("Pa", "Top fibre bending stress", default_factory=list, summary=False)
    sigma_bottom: list = rfield("Pa", "Bottom fibre bending stress", default_factory=list, summary=False)

    def plot(self):
        from .plots import beam_results_plot
        return beam_results_plot(self.x, self.deflection, self.slope, self.x_internal, self.shear, self.moment)


def analyze_beam(beam, theory: str = "EB", n_elem: int = 200, force_fem: bool = False) -> BeamAnalysisResult:
    """
    Analyse a single-span beam.

    Statically determinate beams with Euler-Bernoulli theory are solved by equilibrium;
    indeterminate beams, Timoshenko theory (``theory="TB"``) or ``force_fem=True`` use FEM.
    """
    degree = static_determinacy(beam)
    if degree < 0:
        raise ValueError(f"Beam is a mechanism (degree {degree}): add supports so it can carry load")

    if degree == 0:
        verdict = "Statically determinate: equilibrium (ΣFy = 0, ΣM = 0) gives the reactions"
    else:
        verdict = f"Statically indeterminate to degree {degree}: compatibility needed, FEM required"

    use_equilibrium = (degree == 0 and theory == "EB" and not force_fem
                       and DeterminateSolver.supports(beam.left_end, beam.right_end))
    if use_equilibrium:
        solver = DeterminateSolver(beam)
        R = solver.reactions()
        xi, V, M = solver.shear_moment(n_elem * 2 + 1)
        x, theta, v = solver.deflection(n_elem * 2 + 1)
        method = "Equilibrium (closed form) + double integration of EI v'' = M"
    else:
        solver = FEMSolver(beam, n_elem, theory=theory)
        solver.solve()
        R = solver.reactions()
        x, v = solver.deflection()
        theta = solver.rotation()[1]
        xi, V, M = solver.bending_moment_shear()
        method = f"FEM ({'Euler-Bernoulli' if theory == 'EB' else 'Timoshenko'}, {n_elem} elements)"

    shape = beam.shape
    v, V, M = np.asarray(v), np.asarray(V), np.asarray(M)
    i_v, i_V, i_M = int(np.argmax(np.abs(v))), int(np.argmax(np.abs(V))), int(np.argmax(np.abs(M)))
    M_max = float(abs(M[i_M]))
    sigma = M_max * max(shape.c_top, shape.c_bottom) / shape.Iyy
    fy = beam.material.yield_strength
    return BeamAnalysisResult(
        verdict=verdict, method=method, degree_of_indeterminacy=degree,
        Ay=R.get("Ay", math.nan), MA=R.get("MA", math.nan), By=R.get("By", math.nan), MB=R.get("MB", math.nan),
        max_deflection=float(abs(v[i_v])), max_moment=M_max, max_shear=float(abs(V[i_V])),
        max_bending_stress=sigma, utilisation=sigma / fy if fy else math.nan,
        x_max_deflection=float(np.asarray(x)[i_v]), x_max_moment=float(np.asarray(xi)[i_M]),
        x_max_shear=float(np.asarray(xi)[i_V]), yield_strength=fy or math.nan, section=shape.name,
        c_top=float(shape.c_top), c_bottom=float(shape.c_bottom),
        x=np.asarray(x).tolist(), deflection=np.asarray(v).tolist(), slope=np.asarray(theta).tolist(),
        x_internal=np.asarray(xi).tolist(), shear=np.asarray(V).tolist(), moment=np.asarray(M).tolist(),
        sigma_top=(-M * shape.c_top / shape.Iyy).tolist(), sigma_bottom=(M * shape.c_bottom / shape.Iyy).tolist(),
    )
