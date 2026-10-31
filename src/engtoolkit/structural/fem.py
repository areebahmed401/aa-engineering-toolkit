"""
2D beam finite elements (Euler-Bernoulli and Timoshenko).

Assumptions: linear elastic, small deflections, prismatic beam, bending about the y-axis
(uses shape.Iyy), any end-condition combination.

Sign convention (see loads.py): P, w positive downward; applied M positive counter-clockwise;
v positive upward; sagging moment positive; V = dM/dx; reactions positive upward / counter-clockwise.
"""
from __future__ import annotations

import numpy as np

from .loads import DistributedLoad, MomentLoad, PointLoad


def _hermite(xi, Le):
    """Cubic Hermite shape functions N and their x-derivative dN/dx at xi in [0, 1]."""
    N = np.array([
        1 - 3*xi**2 + 2*xi**3,
        Le * (xi - 2*xi**2 + xi**3),
        3*xi**2 - 2*xi**3,
        Le * (-xi**2 + xi**3),
    ])
    dN = np.array([
        (-6*xi + 6*xi**2) / Le,
        1 - 4*xi + 3*xi**2,
        (6*xi - 6*xi**2) / Le,
        -2*xi + 3*xi**2,
    ])
    return N, dN


class FEMSolver:
    def __init__(self, beam, n_elem=20, theory="EB", nu=None, kappa=5/6):
        """theory: "EB" (Euler-Bernoulli) or "TB" (Timoshenko, shear correction factor kappa)."""
        self.beam = beam
        self.n_elem = n_elem
        self.theory = theory

        self.L = beam.length
        self.E = beam.E
        self.I = beam.shape.Iyy
        self.A = beam.shape.area

        self.G = self.E / (2 * (1 + nu)) if nu is not None else beam.material.G
        self.kappa = kappa

        self.n_nodes = n_elem + 1
        self.ndof = 2 * self.n_nodes
        self.Le = self.L / n_elem
        self.x = np.linspace(0, self.L, self.n_nodes)

        self.K = np.zeros((self.ndof, self.ndof))
        self.F = np.zeros(self.ndof)
        self.F_elem = np.zeros((n_elem, 4))  # equivalent nodal loads per element

        self._assemble_stiffness()
        self._assemble_loads()
        self._apply_boundary_conditions()
        self.U = None

    # ---------------------- Internal Methods ----------------------
    def _element_stiffness(self, Le):
        EI = self.E * self.I
        if self.theory == "EB":
            return EI / Le**3 * np.array([
                [12, 6*Le, -12, 6*Le],
                [6*Le, 4*Le**2, -6*Le, 2*Le**2],
                [-12, -6*Le, 12, -6*Le],
                [6*Le, 2*Le**2, -6*Le, 4*Le**2]
            ])
        phi = 12 * EI / (self.kappa * self.G * self.A * Le**2)
        fac = EI / (Le**3 * (1 + phi))
        return fac * np.array([
            [12, 6*Le, -12, 6*Le],
            [6*Le, (4+phi)*Le**2, -6*Le, (2-phi)*Le**2],
            [-12, -6*Le, 12, -6*Le],
            [6*Le, (2-phi)*Le**2, -6*Le, (4+phi)*Le**2]
        ])

    def _assemble_stiffness(self):
        self.ke = self._element_stiffness(self.Le)
        for e in range(self.n_elem):
            dofs = [2*e, 2*e+1, 2*e+2, 2*e+3]
            self.K[np.ix_(dofs, dofs)] += self.ke

    def _locate(self, x):
        """Element index and local coordinate xi for a position along the beam."""
        e = min(int(x / self.Le), self.n_elem - 1)
        xi = (x - e * self.Le) / self.Le
        return e, xi

    def _assemble_loads(self):
        Le = self.Le
        gauss_pts, gauss_w = np.polynomial.legendre.leggauss(3)
        for load in self.beam.loads:
            if isinstance(load, PointLoad):
                e, xi = self._locate(load.x)
                N, _ = _hermite(xi, Le)
                self.F_elem[e] -= load.P * N
            elif isinstance(load, DistributedLoad):
                x2_load = load.x2 if load.x2 is not None else self.L
                for e in range(self.n_elem):
                    a = max(load.x1, e * Le)
                    b = min(x2_load, (e + 1) * Le)
                    if b <= a:
                        continue
                    # Consistent nodal loads: integral of N(x) * w over the loaded part
                    for gp, gw in zip(gauss_pts, gauss_w):
                        xg = 0.5 * (b - a) * gp + 0.5 * (a + b)
                        N, _ = _hermite((xg - e * Le) / Le, Le)
                        self.F_elem[e] -= load.w * N * gw * 0.5 * (b - a)
            elif isinstance(load, MomentLoad):
                e, xi = self._locate(load.x)
                _, dN = _hermite(xi, Le)
                self.F_elem[e] += load.M * dN

        for e in range(self.n_elem):
            self.F[[2*e, 2*e+1, 2*e+2, 2*e+3]] += self.F_elem[e]

    def _apply_boundary_conditions(self):
        constrained = list(self.beam.left_end.constrained_dofs())
        constrained += [self.ndof - 2 + d for d in self.beam.right_end.constrained_dofs()]
        self.constrained_dofs = np.array(constrained, dtype=int)
        self.free_dofs = np.setdiff1d(np.arange(self.ndof), constrained)

    # ---------------------- Solve ----------------------
    def solve(self):
        Kff = self.K[np.ix_(self.free_dofs, self.free_dofs)]
        Ff = self.F[self.free_dofs]
        try:
            Uf = np.linalg.solve(Kff, Ff)
        except np.linalg.LinAlgError:
            raise ValueError("Beam is a mechanism (not enough supports to resist the loads)") from None
        self.U = np.zeros(self.ndof)
        self.U[self.free_dofs] = Uf
        return self.U

    def deflection(self):
        return self.x, self.U[0::2]

    def rotation(self):
        return self.x, self.U[1::2]

    def reactions(self):
        """Support reactions {'Ay', 'MA', 'By', 'MB'} from R = K U - F at constrained DOFs."""
        R = self.K @ self.U - self.F
        names = {0: "Ay", 1: "MA", self.ndof - 2: "By", self.ndof - 1: "MB"}
        return {names[d]: float(R[d]) for d in self.constrained_dofs}

    # ---------------------- Bending Moment and Shear ----------------------
    def bending_moment_shear(self):
        """
        Shear force and bending moment from element end forces q = ke u - f.
        Exact at the nodes for both EB and Timoshenko elements; linear in between.
        Returns x, V, M (two points per element so jumps are kept).
        """
        xs, Vs, Ms = [], [], []
        for e in range(self.n_elem):
            dofs = [2*e, 2*e+1, 2*e+2, 2*e+3]
            q = self.ke @ self.U[dofs] - self.F_elem[e]
            xs.extend([self.x[e], self.x[e + 1]])
            Vs.extend([q[0], -q[2]])
            Ms.extend([-q[1], q[3]])
        return np.array(xs), np.array(Vs), np.array(Ms)

    def plot_results(self):
        """Deflection, slope, shear and moment diagrams (returns a matplotlib Figure)."""
        from .plots import beam_results_plot
        x_v, v = self.deflection()
        xm, V, M = self.bending_moment_shear()
        return beam_results_plot(x_v, v, self.rotation()[1], xm, V, M)
