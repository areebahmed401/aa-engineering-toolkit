import math
import numpy as np
from CoolProp.CoolProp import PropsSI
import matplotlib.pyplot as plt

class Pipe:
    def __init__(self, diameter, length, material, temperature = None):
        self.D = diameter   # [m]
        self.L = length     # [m]
        self.material = material
        self.temp= temperature

    @property
    def area(self):
        return math.pi * self.D**2 / 4
    
    @property
    def surface_area_per_m(self):
        return math.pi*self.D


class PipeFlow:
    def __init__(self, pipe, fluid_name, T, P):
        """
        fluid_name: CoolProp fluid string, e.g. 'Water', 'Air', 'R134a'
        T: temperature [K]
        P: pressure [Pa]
        """
        self.pipe = pipe
        self.fluid = fluid_name
        self.T = T
        self.P = P

    @property
    def density(self):
        return PropsSI("D", "T", self.T, "P", self.P, self.fluid)

    @property
    def viscosity(self):
        return PropsSI("V", "T", self.T, "P", self.P, self.fluid)

    def velocity(self, Q):
        return Q / self.pipe.area

    def reynolds(self, Q):
        return (
            self.density
            * self.velocity(Q)
            * self.pipe.D
            / self.viscosity
        )

    def colebrook_white(self, Re, roughness, D, tol=1e-6, max_iter=5000):
        """
        Colebrook–White equation for Darcy friction factor.
        """
        if Re <= 0:
            raise ValueError("Reynolds number must be positive")

        if Re <= 2300:
            return 64.0 / Re

        eps_D = roughness / D
        f = 0.02  # good engineering initial guess

        for _ in range(max_iter):
            inv_sqrt_f = 1.0 / math.sqrt(f)
            rhs = -2.0 * math.log10(
                eps_D / 3.7 + 2.51 / (Re * math.sqrt(f))
            )

            if abs(inv_sqrt_f - rhs) < tol:
                return f

            f = 1.0 / rhs**2

        raise RuntimeError("Colebrook–White did not converge")
    
    def friction_factor(self, Q):
        Re = self.reynolds(Q)
        return self.colebrook_white(
            Re,
            roughness=self.pipe.material.roughness,
            D=self.pipe.D
        )
        

    def pressure_drop(self, Q):
        f = self.friction_factor(Q)
        v = self.velocity(Q)

        return (
            f
            * (self.pipe.L / self.pipe.D)
            * 0.5
            * self.density
            * v**2
        )

class PipeSizer:
    def __init__(self, fluid_name, material, T, P, length, catalog_path=None):
        self.fluid_name = fluid_name
        self.material = material
        self.T = T
        self.P = P
        self.length = length
        if catalog_path:
            self.pipe_catalog = load_pipe_catalog(catalog_path)
        else:
            self.pipe_catalog = {}

    def size_for_max_velocity(self, Q, v_max):
        """
        Analytical sizing based on velocity limit
        """
        return (4 * Q / (np.pi * v_max)) ** 0.5

    def size_for_max_dp(self, Q, dp_max, diameters):
        """
        Iterative sizing based on pressure drop
        """
        for D in diameters:
            pipe = Pipe(D, self.length, self.material)
            flow = PipeFlow(pipe, self.fluid, self.T, self.P)

            if flow.pressure_drop(Q) <= dp_max:
                return D

        raise ValueError("No diameter satisfies pressure drop constraint")
    
    def plot_performance_vs_size(self, min_D, max_D, Q=0.01, fittings=None, catalog=None):
            """
            Plot pressure drop, velocity, and pipeline cost vs pipe size.
            """
            # Use provided catalog or class catalog
            pipe_catalog = catalog if catalog is not None else self.pipe_catalog
            if not pipe_catalog:
                raise ValueError("Pipe catalog is empty. Provide catalog or set catalog_path in constructor.")

            if fittings is None:
                fittings = [("elbow_90_standard", 2), ("tee_straight", 1), ("tee_branch", 1)]

            crane_data = load_crane_data("./../utils/Catalogs/equivalent_lengths.csv")

            # Filter pipe sizes in range
            pipe_sizes = [size for size, props in pipe_catalog.items()
                        if min_D <= props["inner_D"] <= max_D]

            dp_list = []
            v_list = []
            cost_list = []

            for size in pipe_sizes:
                D_inner = pipe_catalog[size]["inner_D"]
                pipe = Pipe(diameter=D_inner, length=self.length, material=self.material)
                flow = PipeFlow(pipe, fluid_name=self.fluid_name, T=self.T, P=self.P)

                # Build pipeline with major and minor losses
                line = PipeLine()
                line.add(PipeElement(flow))
                for fitting_name, count in fittings:
                    line.add(CraneMinorLoss(fitting_name, flow, crane_data, count=count))

                dp_list.append(line.total_pressure_drop(Q) / 1000)  # kPa
                v_list.append(flow.velocity(Q))
                cost_list.append(self.calculate_pipeline_cost(size, fittings, catalog=pipe_catalog))

            # Plot
            fig, ax1 = plt.subplots(figsize=(12, 6))
            ax1.set_xlabel("Pipe Size DN [mm]")
            ax1.set_ylabel("Pressure Drop [kPa]", color="tab:red")
            ax1.plot(pipe_sizes, dp_list, "o-", color="tab:red", label="Pressure Drop")
            ax1.tick_params(axis="y", labelcolor="tab:red")
            ax1.grid(True, which="both", linestyle="--", alpha=0.5)

            ax2 = ax1.twinx()
            ax2.set_ylabel("Velocity [m/s]", color="tab:blue")
            ax2.plot(pipe_sizes, v_list, "s--", color="tab:blue", label="Velocity")
            ax2.tick_params(axis="y", labelcolor="tab:blue")

            ax3 = ax1.twinx()
            ax3.spines["right"].set_position(("outward", 60))  # offset third axis
            ax3.set_ylabel("Pipeline Cost [USD]", color="tab:green")
            ax3.plot(pipe_sizes, cost_list, "d-.", color="tab:green", label="Cost")
            ax3.tick_params(axis="y", labelcolor="tab:green")

            fig.suptitle(f"Pressure Drop, Velocity & Cost vs Pipe Size\nQ={Q} m³/s, Fluid={self.fluid_name}, Material ={self.material.name}")
            fig.tight_layout()
            plt.show()
    
    def calculate_pipeline_cost(self, pipe_size, fittings=None, catalog=None):
        """
        Calculate total cost of the pipeline for a selected pipe size in USD.
        """
        pipe_catalog = catalog if catalog is not None else self.pipe_catalog

        if pipe_size not in pipe_catalog:
            raise ValueError(f"Pipe size {pipe_size} not found in catalog.")

        # Pipe cost in USD
        cost_per_m = pipe_catalog[pipe_size]["usd_per_m"]
        pipe_cost = cost_per_m * self.length

        # # Minor fittings cost in USD
        # fittings_cost = 0
        # if fittings:
        #     for fitting_name, count in fittings:
        #         # Assume USD per fitting is stored in catalog (fallback to ksh_per_piece converted to USD)
        #         if fitting_name in pipe_catalog[pipe_size]:
        #             fittings_cost += pipe_catalog[pipe_size][fitting_name] * count
        #         else:
        #             # fallback: convert ksh to USD (or assume already USD)
        #             fittings_cost += pipe_catalog[pipe_size]["ksh_per_piece"] * count /150 # convert to USD

        total_cost = pipe_cost 
        return total_cost
    
#------------ FLOW ELEMENTS: Pipe & Fittings/Valves ------------

from abc import ABC, abstractmethod

class FlowElement(ABC):
    @abstractmethod
    def pressure_drop(self, Q):
        pass
    
class PipeElement(FlowElement): #pressure low due to pipe roughness
    def __init__(self, pipe_flow):
        self.flow = pipe_flow

    def pressure_drop(self, Q):
        return self.flow.pressure_drop(Q)
    
class CraneMinorLoss(FlowElement): # pressure drop due to fittings via Crane-410
    def __init__(self, fitting_type, pipe_flow, K_data, count=1):
        self.pipe_flow = pipe_flow
        self.count = count

        try:
            self.Le_over_D = K_data[fitting_type]
        except KeyError:
            raise ValueError(f"Unknown Crane fitting: {fitting_type}")

    def pressure_drop(self, Q):
        f = self.pipe_flow.friction_factor(Q)
        rho = self.pipe_flow.density
        v = self.pipe_flow.velocity(Q)

        K = f * self.Le_over_D
        return self.count * K * 0.5 * rho * v**2

    
class PipeLine: #complete pipe line
    def __init__(self):
        self.elements = []

    def add(self, element):
        self.elements.append(element)

    def add_many(self, element_class, n, *args, **kwargs):
        for _ in range(n):
            self.add(element_class(*args, **kwargs))

    def total_pressure_drop(self, Q):
        return sum(e.pressure_drop(Q) for e in self.elements)


#------ CATALOG LOADERs---------------------------------------
import csv

def load_crane_data(csv_path):
    data = {}
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            data[row["fitting_type"]] = float(row["Le_over_D"])
    return data

def load_pipe_catalog(csv_path):
    data = {}
    with open(csv_path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data[int(row["size"])] = {
                "inner_D": float(row["inner_D"]),
                "outer_D": float(row["outer_D"]),
                "ksh_per_piece": float(row["ksh_per_piece"]),
                "usd_per_m": float(row["usd_per_m"])
            }
    return data

