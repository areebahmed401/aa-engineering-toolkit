import math
import numpy as np


def colebrook_white(Re,roughness, D):
   
    epsilon_D = roughness / D    
    # Initial guess for f
    f = 0.001
    # Maximum number of iterations
    max_iter = 5000
    # Tolerance for convergence
    tol = 1e-6
    # Iteration counter
    iter_count = 0
    while True:
        # Calculate the left-hand side of the Colebrook-White equation
        lhs = 1 / math.sqrt(f)
        # Calculate the right-hand side of the Colebrook-White equation
        rhs = -2 * math.log10((epsilon_D / 3.7) + (2.51 / (Re * math.sqrt(f))))
        # Check for convergence
        if abs(lhs - rhs) < tol or iter_count >= max_iter:
            break
        # Update f
        f = 1 / (rhs ** 2)
        # Increment iteration counter
        iter_count += 1
    return f

def convert_headtobar(h, density):
    P= 9.81*density*h/100000
    return P

def darcy_weisbach(f, distance, velocity, diameter):
    loss= f * (distance * 1000) * (velocity ** 2) / (2 * diameter*9.81)
    # print("Darcy-Weisbach loss: {} bar".format(loss))
    return loss #in m of head

def get_h_minor(f, distance, velocity, diameter):
    loss= f * (distance * 1000) * (velocity ** 2) / (2 * diameter*9.81)
    return loss

def get_h_major(n_elbow, n_valve, length):
    n_expansion_loop= length/150*1000
    Le_D_elbow=13
    Le_D_valve = 7.2
    # Le_D_rTee= 57
    # Le_D_expansion_loop= 4*Le_D_elbow + 1.5
    
    loss= Le_D_elbow*n_elbow + Le_D_valve*n_valve+ n_expansion_loop #in mm
    return loss

def get_Le_reducer(n,Do,Di):
    x=(Do/Di)*2
    if x >0.9:
        Le = 2.0
    elif x > 0.7:
        Le = 16
    else:
        Le=38
        
    Loss = n*Le*Di # in mm
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