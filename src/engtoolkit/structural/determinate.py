"""Statically determinate beams solved from equilibrium (simply supported or cantilever)."""
from __future__ import annotations

import numpy as np

from .loads import DistributedLoad, Fixed, Free, MomentLoad, Pinned, PointLoad, Roller


class DeterminateSolver:

    def __init__(self, beam):
        self.beam = beam
        self.L = beam.length
        self.loads = beam.loads
        self.left = beam.left_end
        self.right = beam.right_end

    def _load_resultants(self):
        """Total downward force and its clockwise moment about the left end (incl. applied moments)."""
        Fy = 0.0
        M_about_A = 0.0  # clockwise positive moment of the loads about x = 0
        for load in self.loads:
            if isinstance(load, PointLoad):
                Fy += load.P
                M_about_A += load.P * load.x
            elif isinstance(load, DistributedLoad):
                x1 = load.x1
                x2 = load.x2 if load.x2 is not None else self.L
                W = load.w * (x2 - x1)
                Fy += W
                M_about_A += W * 0.5 * (x1 + x2)
            elif isinstance(load, MomentLoad):
                M_about_A -= load.M  # counter-clockwise applied moment
        return Fy, M_about_A

    @staticmethod
    def supports(left, right) -> bool:
        """True if this solver handles the support combination."""
        s = (Pinned, Roller)
        return (isinstance(left, s) and isinstance(right, s)) or \
               (isinstance(left, Fixed) and isinstance(right, Free)) or \
               (isinstance(left, Free) and isinstance(right, Fixed))

    def reactions(self):
        """
        Reactions for statically determinate single-span beams:
        simply supported (pinned/roller at both ends) or a cantilever fixed at either end.
        Returns a dict with 'Ay', 'By', 'MA', 'MB' as applicable.
        """
        supported = (Pinned, Roller)
        Fy, M_A = self._load_resultants()
        L = self.L

        if isinstance(self.left, supported) and isinstance(self.right, supported):
            By = M_A / L
            return {"Ay": Fy - By, "By": By}
        if isinstance(self.left, Fixed) and isinstance(self.right, Free):
            return {"Ay": Fy, "MA": M_A}
        if isinstance(self.left, Free) and isinstance(self.right, Fixed):
            return {"By": Fy, "MB": M_A - Fy * L}

        raise ValueError(
            "DeterminateSolver handles simply supported beams and cantilevers only; "
            "use FEMSolver for statically indeterminate supports."
        )

    def shear_moment(self, n=400):
        """Shear V(x) and sagging-positive bending moment M(x) from a left free body."""
        x = np.linspace(0, self.L, n)
        R = self.reactions()
        Ay = R.get("Ay", 0.0)
        MA = R.get("MA", 0.0)

        V = np.full_like(x, Ay)
        M = Ay * x - MA

        for load in self.loads:
            if isinstance(load, PointLoad):
                past = x >= load.x
                V -= load.P * past
                M -= load.P * (x - load.x) * past
            elif isinstance(load, DistributedLoad):
                x1 = load.x1
                x2 = load.x2 if load.x2 is not None else self.L
                Lw = np.clip(x - x1, 0.0, x2 - x1)  # loaded length left of the cut
                V -= load.w * Lw
                M -= load.w * Lw * (x - x1 - Lw / 2)
            elif isinstance(load, MomentLoad):
                M -= load.M * (x >= load.x)  # counter-clockwise moment: jump down in M

        return x, V, M

    def deflection(self, n=400):
        """
        Slope and deflection from EI v'' = M(x), integrated with the trapezoidal rule
        and the two integration constants set by the supports.
        """
        x, _, M = self.shear_moment(n)
        EI = self.beam.E * self.beam.shape.Iyy

        curvature = M / EI
        theta_p = np.concatenate(([0.0], np.cumsum(0.5 * (curvature[1:] + curvature[:-1]) * np.diff(x))))
        v_p = np.concatenate(([0.0], np.cumsum(0.5 * (theta_p[1:] + theta_p[:-1]) * np.diff(x))))

        # v = v_p + C1 x + C2, theta = theta_p + C1
        if isinstance(self.left, Fixed):           # v(0) = 0, theta(0) = 0
            C1, C2 = 0.0, 0.0
        elif isinstance(self.right, Fixed):        # v(L) = 0, theta(L) = 0
            C1 = -theta_p[-1]
            C2 = -v_p[-1] - C1 * self.L
        else:                                      # v(0) = 0, v(L) = 0
            C2 = 0.0
            C1 = -v_p[-1] / self.L

        return x, theta_p + C1, v_p + C1 * x + C2

    def plot(self):
        """Deflection, slope, shear and moment diagrams (returns a matplotlib Figure)."""
        from .plots import beam_results_plot
        x, V, M = self.shear_moment()
        xd, theta, v = self.deflection()
        return beam_results_plot(xd, v, theta, x, V, M)
