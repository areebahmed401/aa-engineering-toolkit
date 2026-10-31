import math
import numpy as np


def colebrook_white(Re, roughness, D, tol=1e-6, max_iter=5000):
    """
    Darcy friction factor [-] from the Colebrook-White equation.

    Re        : Reynolds number [-]
    roughness : absolute pipe roughness [m]
    D         : inner diameter [m]
    Laminar flow (Re <= 2300) returns 64/Re.
    """
    if Re <= 0:
        raise ValueError("Reynolds number must be positive")
    if Re <= 2300:
        return 64.0 / Re

    epsilon_D = roughness / D
    f = 0.02  # good engineering initial guess
    for _ in range(max_iter):
        lhs = 1 / math.sqrt(f)
        rhs = -2 * math.log10((epsilon_D / 3.7) + (2.51 / (Re * math.sqrt(f))))
        if abs(lhs - rhs) < tol:
            return f
        f = 1 / (rhs ** 2)
    raise RuntimeError("Colebrook-White did not converge")


def fully_turbulent_friction_factor(roughness, D):
    """
    Fully turbulent Darcy friction factor f_T [-] (rough-pipe limit of Colebrook).
    Used with Crane TP-410 L/D values: K = f_T * (L/D).
    """
    return 0.25 / math.log10(roughness / (3.7 * D)) ** 2

def convert_headtobar(h, density):
    """Head h [m] of a fluid with density [kg/m³] to pressure [bar]."""
    P= 9.81*density*h/100000
    return P

def darcy_weisbach(f, distance, velocity, diameter):
    """Head loss [m] over a length distance [m] of pipe with inner diameter [m]."""
    loss= f * distance * (velocity ** 2) / (2 * diameter*9.81)
    return loss #in m of head

def get_h_major(f, distance, velocity, diameter):
    """Major (friction) head loss [m]; same as darcy_weisbach."""
    return darcy_weisbach(f, distance, velocity, diameter)

def get_Le_minor(n_elbow, n_valve, length, diameter):
    """
    Equivalent length [m] of fittings (minor losses) for a line of the given length [m].
    Uses L/D = 13 per elbow, 7.2 per valve and one expansion loop every 150 m
    (4 elbows each).
    """
    Le_D_elbow = 13
    Le_D_valve = 7.2
    n_expansion_loop = length / 150
    Le_D = Le_D_elbow * (n_elbow + 4 * n_expansion_loop) + Le_D_valve * n_valve
    return Le_D * diameter

def get_Le_reducer(n, Do, Di):
    """
    Equivalent length [same unit as Di] of n reducers from Do to Di,
    picked from the area ratio beta² = (Di/Do)².
    """
    beta_sq = (Di / Do) ** 2
    if beta_sq > 0.9:
        Le = 2.0
    elif beta_sq > 0.7:
        Le = 16
    else:
        Le=38

    Loss = n*Le*Di
    return Loss

#determine the nusselt number for steam
def nusselt_number(Re, Pr):
    if Re < 2300:
        Nu = 3.66
    elif Re > 2300 and Re < 10000:
        Nu = 4.36
    else:
        Nu = 0.023 * (Re ** 0.8) * (Pr ** 0.4)
    return Nu

#determine the heat transfer coefficient of steam from nusselt number
def heat_transfer_coefficient(Nu, thermal_conductivity, diameter):
    h = Nu * thermal_conductivity / diameter
    return h

#determine the reynolds number
def reynolds_number(density, velocity, diameter, viscosity):
    Re = density * velocity * diameter / viscosity
    return Re

#determine the prandtl number
def prandtl_number(viscosity, specific_heat, thermal_conductivity):
    Pr = viscosity * specific_heat / thermal_conductivity
    return Pr

#determine LMTD of HE
def LMTD(T_hot_in, T_hot_out, T_cold_in, T_cold_out):
    delta_T1 = T_hot_in - T_cold_out
    delta_T2 = T_hot_out - T_cold_in
    LMTD = (delta_T1 - delta_T2) / np.log(delta_T1 / delta_T2)
    return LMTD

def pipe_X_area(diameter):
    A = math.pi * (diameter ** 2) / 4
    return A

def pipe_area(diameter):
    A = math.pi * diameter
    return A

def R_pipe_convective(h, A):
    R = 1 / (h * A) #K/W
    return R

def R_pipe_conductive(outer_radius, inner_radius, thermal_conductivity):
    R= math.log(outer_radius / inner_radius) / (2 * math.pi * thermal_conductivity ) #K/W
    return R

def get_wet_bulb_temperature(T_d, RH):
   
    T_w = T_d * math.atan(0.151977 * math.sqrt(RH + 8.313659)) \
          + math.atan(T_d + RH) \
          - math.atan(RH - 1.676331) \
          + 0.00391838 * RH**1.5 * math.atan(0.023101 * RH) \
          - 4.686035

    return round(T_w, 2)