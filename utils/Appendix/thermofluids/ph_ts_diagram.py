import CoolProp.CoolProp as CP
import matplotlib.pyplot as plt
import numpy as np

def plot_saturated_lines(fluid='Water'):
    # Calculate saturation properties over a wider pressure range
    saturation_pressure = np.linspace(1, 100000, 1000)  # Pressure range (kPa)

    # Dry saturated line
    saturation_enthalpy_dry = CP.PropsSI('H', 'P', saturation_pressure * 1e3, 'Q', 0, fluid) / 1000
    saturation_entropy_dry = CP.PropsSI('S', 'P', saturation_pressure * 1e3, 'Q', 0, fluid) / 1000
    saturation_temperature_dry = CP.PropsSI('T', 'P', saturation_pressure * 1e3, 'Q', 0, fluid)

    # Wet saturated line
    saturation_enthalpy_wet = CP.PropsSI('H', 'P', saturation_pressure * 1e3, 'Q', 1, fluid) / 1000
    saturation_entropy_wet = CP.PropsSI('S', 'P', saturation_pressure * 1e3, 'Q', 1, fluid) / 1000
    saturation_temperature_wet = CP.PropsSI('T', 'P', saturation_pressure * 1e3, 'Q', 1, fluid)

    # Critical point properties
    critical_temperature = CP.PropsSI('Tcrit', fluid)  # Critical temperature (K)
    critical_pressure = CP.PropsSI('Pcrit', fluid) / 1e3  # Critical pressure (kPa)

    # Plotting the saturated lines
    plt.figure(figsize=(12, 7))

    # Pressure-Enthalpy (p-h) diagram
    plt.subplot(1, 2, 1)

    # Plot dry saturated line
    plt.plot(saturation_enthalpy_dry, saturation_pressure, 'b-', label='Dry Saturated Line')

    # Plot wet saturated line
    plt.plot(saturation_enthalpy_wet, saturation_pressure, 'r-', label='Wet Saturated Line')

    # Plot critical point
    plt.plot(CP.PropsSI('H', 'P', critical_pressure * 1e3, 'T', critical_temperature, fluid) / 1000, 
             critical_pressure, 'ko', label='Critical Point')

    # Plot isothermal lines and add temperature callouts
    isothermal_temperatures = np.linspace(300, critical_temperature - 5, 50)  # temperatures in Kelvin
    for T in isothermal_temperatures:
        enthalpies = []
        pressures = []
        for p in saturation_pressure:
            try:
                h = CP.PropsSI('H', 'T', T, 'P', p * 1e3, fluid) / 1000
                p_sat= CP.PropsSI('P', 'T', T, 'Q', 0, fluid) / 1e3
                h_dry = CP.PropsSI('H', 'P', p_sat * 1e3, 'Q', 1, fluid) / 1000
                h_wet = CP.PropsSI('H', 'P', p_sat * 1e3, 'Q', 0, fluid) / 1000
                h_plot = np.average([h_dry, h_wet])
                enthalpies.append(h)
                pressures.append(p)
            except ValueError:
                pass
        plt.plot(enthalpies, pressures, 'g--', alpha=0.5)
        
        # Add callouts for temperature
        if enthalpies and pressures:
            plt.text(h_plot, p_sat, f'{T:.1f} K', fontsize=8, ha='right', va='bottom', color='green')

    # Labels and title
    plt.xlabel('Enthalpy (kJ/kg)')
    plt.ylabel('Pressure (kPa)')
    plt.title('{} P-H Diagram'.format(fluid))
    plt.ylim(0, critical_pressure + 5000)
    plt.grid(True)
    plt.legend()

    # Temperature-Entropy (T-S) diagram
    plt.subplot(1, 2, 2)

    # Plot dry saturated line
    plt.plot(saturation_entropy_dry, saturation_temperature_dry, 'b-', label='Dry Saturated Line')

    # Plot wet saturated line
    plt.plot(saturation_entropy_wet, saturation_temperature_wet, 'r-', label='Wet Saturated Line')

    # Plot critical point
    plt.plot(CP.PropsSI('S', 'P', critical_pressure * 1e3, 'T', critical_temperature, fluid) / 1000, 
             critical_temperature, 'ko', label='Critical Point')

    # Plot isobaric lines
    isobaric_pressures = np.linspace(10,20000,10)  # pressures in MPa
    for P in isobaric_pressures:
        entropies = []
        temperatures = []
        for T in np.linspace(273.15, critical_temperature, 100):
            try:
                s = CP.PropsSI('S', 'T', T, 'P', P * 1e3, fluid) / 1000
                t_sat= CP.PropsSI('T', 'P', P * 1e3, 'Q', 0, fluid)
                s_dry = CP.PropsSI('S', 'P', P * 1e3, 'Q', 1, fluid) / 1000
                s_wet = CP.PropsSI('S', 'P', P * 1e3, 'Q', 0, fluid) / 1000
                s_plot = np.average([s_dry, s_wet])
                entropies.append(s)
                temperatures.append(T)
            except ValueError:
                pass
        plt.plot(entropies, temperatures, 'g--', alpha=0.5)
        
        # Add callouts for pressure
        if entropies and temperatures:
            plt.text(s_plot, t_sat, f'{P:.0f} kPa', fontsize=8, ha='right', va='bottom', color='green')

    # Labels and title
    plt.xlabel('Entropy (kJ/(kg K))')
    plt.ylabel('Temperature (K)')
    plt.title('{} T-S Diagram'.format(fluid))
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
   

def plot_processes(p1,p2,h1,h2,t1,t2,s1,s2, fluid='Water'):
    # Plotting the processes
    plot_saturated_lines(fluid)
    
    # Pressure-Enthalpy (p-h) diagram
    plt.subplot(1, 2, 1)

    # Plot initial and final states
    plt.plot(h1, p1, 'rx', label='Initial State')
    plt.plot(h2, p2, 'bx', label='Final State')

    # Plot a line connecting initial and final states (representing the pressure drop)
    plt.plot([h1, h2], [p1, p2], 'k--', label='Pressure Drop')

    # Labels and title
    plt.xlabel('Enthalpy (kJ/kg)')
    plt.ylabel('Pressure (kPa)')
    plt.title('Water p-h Diagram - Processes')
    # plt.ylim(0, 0.42)
    plt.grid(True)
    plt.legend()

    # Temperature-Entropy (T-S) diagram
    plt.subplot(1, 2, 2)

    # Plot initial and final states
    plt.plot(s1 , t1, 'rx', label='Initial State')
    plt.plot(s2 , t2, 'bx', label='Final State')
    
    # Plot a line connecting initial and final states (representing the temperature drop)
    plt.plot([s1, s2], [t1, t2], 'k--', label='Temperature Drop')

    # Labels and title
    plt.xlabel('Entropy (kJ/(kg K))')
    plt.ylabel('Temperature (K)')
    plt.title('Water T-S Diagram - Processes')
    plt.grid(True)
    plt.legend()

    plt.tight_layout()
    plt.show()


def plot_flashing_process(p1,p2,t1,fluid='Water'):
        
    # Calculate initial and final state properties using CoolProp
    h_initial = CP.PropsSI('H', 'P', p1 * 1e6, 'T', t1, 'Water') / 1000  # Initial enthalpy (kJ/kg)
    h_final = h_initial # Final enthalpy (kJ/kg)
    s_initial = CP.PropsSI('S', 'P', p1 * 1e6, 'T', t1, 'Water') / 1000  # Initial entropy (kJ/kg-K)
    s_final = CP.PropsSI('S', 'P', p2 * 1e6, 'H', h_final*1000, 'Water') / 1000 # Final entropy (kJ/kg-K)
    print(s_final)
    T_final = CP.PropsSI('T', 'P', p2 * 1e6, 'S', s_final*1000, 'Water')  # Final temperature (K)
    
    plot_processes(p1,p2,h_initial,h_final,t1,T_final,s_initial,s_final, fluid)
    
    
#Flashing process    
plot_flashing_process(0.4,0.08,417)

# Example usage (uncomment the following line to run the example)
# plot_saturated_lines('Ammonia')
# plt.show()