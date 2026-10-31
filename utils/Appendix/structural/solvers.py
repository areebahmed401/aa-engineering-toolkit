"""
====================================================================
GENERAL FEM SOLVER (Euler–Bernoulli + Timoshenko)
====================================================================

Includes:
- General FEM beam solver (any end-condition combination)
- Determinate solver from equilibrium (simply supported / cantilevers)
- Post-processing: deflection, rotation, shear, moment, reactions

Assumptions:
- Linear elastic
- Small deflections
- Prismatic beam
- 2D bending about the y-axis (uses shape.Iyy)

Sign convention (see FBD_beams.py):
- P, w positive downward; applied M positive counter-clockwise
- v positive upward; sagging moment positive; V = dM/dx
- Reactions: forces positive upward, moments positive counter-clockwise

====================================================================
"""

import numpy as np
import matplotlib.pyplot as plt
from .FBD_beams import PointLoad, DistributedLoad, MomentLoad, Fixed, Pinned, Free, Roller


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
        Le = self.L / self.n_elem
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
        constrained = []
        for d in self.beam.left_end.constrained_dofs():
            constrained.append(d)
        for d in self.beam.right_end.constrained_dofs():
            constrained.append(self.ndof - 2 + d)
        self.constrained_dofs = np.array(constrained, dtype=int)
        self.free_dofs = np.setdiff1d(np.arange(self.ndof), constrained)

    # ---------------------- Solve ----------------------
    def solve(self):
        Kff = self.K[np.ix_(self.free_dofs, self.free_dofs)]
        Ff = self.F[self.free_dofs]
        Uf = np.linalg.solve(Kff, Ff)
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
        return {names[d]: R[d] for d in self.constrained_dofs}

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

    # ---------------------- Plot ----------------------
    def plot_results(self, scale_deflection=1.0, scale_shear=1.0, scale_moment=1.0):
        x_defl, v = self.deflection()
        x_ms, V, M = self.bending_moment_shear()

        fig, axs = plt.subplots(4, 1, figsize=(12,12), sharex=True)

        axs[0].plot(x_defl, v*scale_deflection, 'purple', lw=2)
        axs[0].set_ylabel('Deflection [m]')
        axs[0].grid(True)
        axs[0].set_title('Beam Deflection')

        theta = self.rotation()[1]
        axs[1].plot(x_defl, theta, 'orange', lw=2)
        axs[1].set_ylabel('Slope θ [rad]')
        axs[1].grid(True)
        axs[1].set_title('Slope Diagram')

        axs[2].plot(x_ms, V*scale_shear, 'blue', lw=2)
        axs[2].set_ylabel('Shear [N]')
        axs[2].grid(True)
        axs[2].set_title('Shear Force Diagram')

        axs[3].plot(x_ms, M*scale_moment, 'red', lw=2)
        axs[3].set_ylabel('Moment [Nm]')
        axs[3].set_xlabel('Beam Length [m]')
        axs[3].grid(True)
        axs[3].set_title('Bending Moment Diagram')

        plt.tight_layout()
        plt.show()



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

    # ---------------------------------------------------
    # Reactions
    # ---------------------------------------------------
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

    # ---------------------------------------------------
    # Shear & Bending Moment
    # ---------------------------------------------------
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

        theta = theta_p + C1
        v = v_p + C1 * x + C2
        return x, theta, v


    # ---------------------------------------------------
    # Plotting
    # ---------------------------------------------------
    def plot(self):

        # --- Results ---
        x_sm, V, M = self.shear_moment()
        x_def, theta, v = self.deflection()

        fig, ax = plt.subplots(4, 1, figsize=(12, 11), sharex=True)

        # ---------------- DEFLECTION ----------------
        ax[0].plot(x_def, v * 1000, color='purple', linewidth=2)
        ax[0].set_ylabel("Deflection [mm]")
        ax[0].set_title("Deflection Diagram")
        ax[0].grid(True)

        # ---------------- SLOPE ----------------
        ax[1].plot(x_def, theta, color='orange', linewidth=2)
        ax[1].set_ylabel("Slope θ [rad]")
        ax[1].set_title("Slope Diagram")
        ax[1].grid(True)

        # ---------------- SHEAR FORCE ----------------
        ax[2].plot(x_sm, V, linewidth=2)
        ax[2].set_ylabel("Shear Force [N]")
        ax[2].set_title("Shear Force Diagram")
        ax[2].grid(True)

        # ---------------- BENDING MOMENT ----------------
        ax[3].plot(x_sm, M, linewidth=2)
        ax[3].set_xlabel("x [m]")
        ax[3].set_ylabel("Bending Moment [Nm]")
        ax[3].set_title("Bending Moment Diagram")
        ax[3].grid(True)

        plt.tight_layout()
        plt.show()


# ---------------- Example Usage ----------------
# from utils.Appendix.materials import get_material
# from utils.Appendix.structural.members import beam, Rectangle
# from utils.Appendix.structural.FBD_beams import Fixed, Pinned, DistributedLoad, PointLoad
#
# my_beam = beam(material=get_material("Steel"), length=2.0, shape=Rectangle(width=0.1, height=0.2))
# my_beam.set_end_conditions(left=Fixed(), right=Pinned())
# my_beam.add_load(DistributedLoad(w=5000))      # 5 kN/m over full length
# my_beam.add_load(PointLoad(P=10000, x=1.2))    # 10 kN at x=1.2 m
#
# solver = FEMSolver(beam=my_beam, n_elem=50, theory="EB")
# solver.solve()
# print(solver.reactions())
# solver.plot_results()
