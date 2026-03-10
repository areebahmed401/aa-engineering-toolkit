"""
====================================================================
GENERAL FEM SOLVER (Euler–Bernoulli + Timoshenko)
====================================================================

Includes:
- Cross-section hierarchy (original + preserved)
- Beam definition
- Load definitions
- End-condition definitions
- General FEM beam solver
- Post-processing: deflection, rotation, shear, moment

Assumptions:
- Linear elastic
- Small deflections
- Prismatic beam
- 2D bending (about y-axis)
- Any end-condition combination

====================================================================
"""

import numpy as np
import matplotlib.pyplot as plt
from FBD_beams import PointLoad, DistributedLoad, MomentLoad, Fixed, Pinned, Free, Roller


class FEMSolver:
    def __init__(self, beam, n_elem=20, theory="EB", nu=0.3, kappa=5/6):
        self.beam = beam
        self.n_elem = n_elem
        self.theory = theory

        self.L = beam.length
        self.E = beam.E
        self.I = beam.shape.Iy
        self.A = beam.shape.area

        self.G = self.E / (2 * (1 + nu))
        self.kappa = kappa

        self.n_nodes = n_elem + 1
        self.ndof = 2 * self.n_nodes
        self.x = np.linspace(0, self.L, self.n_nodes)

        self.K = np.zeros((self.ndof, self.ndof))
        self.F = np.zeros(self.ndof)

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
        Le = self.L / self.n_elem
        for e in range(self.n_elem):
            ke = self._element_stiffness(Le)
            dofs = [2*e, 2*e+1, 2*e+2, 2*e+3]
            self.K[np.ix_(dofs, dofs)] += ke

    def _assemble_loads(self):
        Le = self.L / self.n_elem
        for load in self.beam.loads:
            if isinstance(load, PointLoad):
                node = int(load.x / self.L * self.n_elem)
                self.F[2*node] -= load.P
            elif isinstance(load, DistributedLoad):
                # distribute load over elements proportionally
                for e in range(self.n_elem):
                    x1 = e * Le
                    x2 = (e+1) * Le
                    overlap = max(0, min(load.x2 if load.x2 else self.L, x2) - max(load.x1, x1))
                    if overlap > 0:
                        fe = load.w * overlap / 2 * np.array([1, Le/6, 1, -Le/6])
                        dofs = [2*e, 2*e+1, 2*e+2, 2*e+3]
                        self.F[dofs] -= fe
            elif isinstance(load, MomentLoad):
                node = int(load.x / self.L * self.n_elem)
                self.F[2*node + 1] -= load.M

    def _apply_boundary_conditions(self):
        constrained = []
        for d in self.beam.left_end.constrained_dofs():
            constrained.append(d)
        for d in self.beam.right_end.constrained_dofs():
            constrained.append(self.ndof - 2 + d)
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

    # ---------------------- Smooth Bending Moment and Shear ----------------------
    def bending_moment_shear(self, points_per_element=50):
        EI = self.E * self.I
        xs_full = []
        Ms_full = []
        Vs_full = []

        Le = self.L / self.n_elem

        for e in range(self.n_elem):
            dofs = [2*e, 2*e+1, 2*e+2, 2*e+3]
            ue = self.U[dofs]  # [v0, theta0, v1, theta1]

            v0, theta0, v1, theta1 = ue
            x_local = np.linspace(0, Le, points_per_element)
            xi = x_local / Le

            # Cubic Hermite shape function second derivative
            N1_dd = 6*xi - 6
            N2_dd = 3*xi - 4
            N3_dd = -6*xi + 6
            N4_dd = 3*xi - 2

            M_x = EI / Le**2 * (v0*N1_dd + theta0*Le*N2_dd + v1*N3_dd + theta1*Le*N4_dd)

            # Shear force = derivative of bending moment (numerical)
            V_x = np.gradient(M_x, x_local)

            xs_full.extend(self.x[e] + x_local)
            Ms_full.extend(M_x)
            Vs_full.extend(V_x)

        return np.array(xs_full), np.array(Vs_full), np.array(Ms_full)

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

    # ---------------------------------------------------
    # Reactions
    # ---------------------------------------------------
    def reactions(self):
        """
        General statically determinate solver for Fx, Fy, and M
        """

        from FBD_beams import Fixed, Pinned, Roller

        L = self.L

        unknowns = {}

        # --- Left support ---
        if isinstance(self.left, (Pinned, Fixed)):
            unknowns["Ax"] = 0.0
        if isinstance(self.left, (Pinned, Roller, Fixed)):
            unknowns["Ay"] = 0.0
        if isinstance(self.left, Fixed):
            unknowns["MA"] = 0.0

        # --- Right support ---
        if isinstance(self.right, (Pinned, Fixed)):
            unknowns["Bx"] = 0.0
        if isinstance(self.right, (Pinned, Roller, Fixed)):
            unknowns["By"] = 0.0
        if isinstance(self.right, Fixed):
            unknowns["MB"] = 0.0

        # --- Check determinacy ---
        if len(unknowns) != 3:
            raise ValueError(
                f"System not statically determinate "
                f"(reaction unknowns = {len(unknowns)})"
            )

        # --------------------------------------------------
        # Resultant external loads
        # --------------------------------------------------
        Fx = 0.0
        Fy = 0.0
        MA = 0.0

        for load in self.loads:

            if isinstance(load, PointLoad):
                Fx += getattr(load, "Px", 0.0)
                Fy += getattr(load, "Py", load.P)
                MA += getattr(load, "Py", load.P) * load.x

            elif isinstance(load, DistributedLoad):
                x1 = load.x1
                x2 = load.x2 if load.x2 else L
                Lw = x2 - x1

                Fx += getattr(load, "wx", 0.0) * Lw
                Fy += load.w * Lw

                xc = 0.5 * (x1 + x2)
                MA += load.w * Lw * xc

            elif isinstance(load, MomentLoad):
                MA += load.M

        results = {}

        # --------------------------------------------------
        # Solve equilibrium
        # --------------------------------------------------
        if "Ay" in unknowns and "By" in unknowns:
            # Simply supported (vertical reactions)
            By = MA / L
            Ay = Fy - By
            results["Ay"] = Ay
            results["By"] = By

        elif "Ay" in unknowns and "MA" in unknowns:
            # Cantilever (left fixed)
            results["Ay"] = Fy
            results["MA"] = MA

        elif "By" in unknowns and "MB" in unknowns:
            # Cantilever (right fixed)
            results["By"] = Fy
            results["MB"] = MA - Fy * L

        # Axial equilibrium
        if "Ax" in unknowns:
            results["Ax"] = Fx
        if "Bx" in unknowns:
            results["Bx"] = Fx

        return results



    # ---------------------------------------------------
    # Shear & Bending Moment
    # ---------------------------------------------------
    def shear_moment(self, n=400):
        x = np.linspace(0, self.L, n)
        V = np.zeros_like(x)
        M = np.zeros_like(x)

        R = self.reactions()
        VA = R.get("A", R.get("V_fixed", 0.0))
        MA = R.get("M_fixed", 0.0)

        for i, xi in enumerate(x):
            # reactions
            V[i] += VA
            M[i] += MA + VA * xi

            for load in self.loads:
                if isinstance(load, PointLoad) and xi >= load.x:
                    V[i] -= load.P
                    M[i] -= load.P * (xi - load.x)

                elif isinstance(load, DistributedLoad):
                    x1 = load.x1
                    x2 = load.x2 if load.x2 else self.L
                    if xi > x1:
                        Lw = min(xi, x2) - x1
                        V[i] -= load.w * Lw
                        M[i] -= load.w * Lw * (xi - x1 - Lw / 2)

                elif isinstance(load, MomentLoad) and xi >= load.x:
                    M[i] -= load.M  # jump in moment ONLY

            # right reaction (simply supported)
            if "B" in R and xi >= self.L:
                V[i] -= R["B"]

        return x, V, M
    
    def deflection(self, n=400):
        """
        Computes slope and deflection using:
        EI v'' = M(x)
        """
        x, _, M = self.shear_moment(n)

        EI = self.beam.E * self.beam.shape.Iy

        dx = x[1] - x[0]

        # Curvature
        curvature = M / EI

        # First integration: slope
        theta = np.zeros_like(x)
        for i in range(1, n):
            theta[i] = theta[i-1] + curvature[i-1] * dx

        # Second integration: deflection
        v = np.zeros_like(x)
        for i in range(1, n):
            v[i] = v[i-1] + theta[i-1] * dx

        # -------------------------------------------------
        # Apply boundary conditions
        # -------------------------------------------------
        left = self.beam.left_end
        right = self.beam.right_end

        # Cantilever: v(0)=0, theta(0)=0 → already satisfied
        if isinstance(left, Fixed):
            pass

        # Simply supported: v(0)=0 and v(L)=0
        if isinstance(left, Pinned) and isinstance(right, Roller):
            # remove rigid-body slope
            v -= v[-1] * x / self.L

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



# # ---------------- Example Usage ----------------

# # 1. Define a cross-section
# beam_shape = beams.Rectangle(width=0.1, height=0.2)  # 10cm x 20cm

# # 2. Define material properties
# from materials import get_material
# beam_material = get_material("Steel")
# E_material = beam_material.E

# # 3. Create beam object
# my_beam = beams.beam(material=beam_material, E=E_material, length=2.0, shape=beam_shape)

# # 4. Set end conditions
# my_beam.set_end_conditions(left=Fixed(), right=Pinned())

# # 5. Add loads
# my_beam.add_load(DistributedLoad(w=5000))      # 5 kN/m over full length
# my_beam.add_load(PointLoad(P=10000, x=1.2))    # 10 kN at x=1.2 m

# # 6. Create FEM solver
# solver = FEMBeamSolver(beam=my_beam, n_elem=50, theory="EB")  # Timoshenko beam

# # 7. Solve
# solver.solve()

# # 8. Post-processing
# x_defl, v = solver.deflection()
# x_rot, theta = solver.rotation()
# x_ms, V, M = solver.moment_shear()

# # 9. Print maximum results
# print(f"Maximum deflection: {v.min():.6e} m")
# print(f"Maximum bending moment: {M.max():.3e} Nm")
# print(f"Maximum shear force: {V.max():.3e} N")

# # 10. Optional: Plot results (requires matplotlib)
# import matplotlib.pyplot as plt

# plt.figure()
# plt.plot(x_defl, v*1000, label='Deflection [mm]')
# plt.xlabel('Beam length [m]')
# plt.ylabel('Deflection [mm]')
# plt.grid(True)
# plt.legend()
# plt.show()
