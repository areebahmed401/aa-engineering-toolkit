import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import CoolProp.CoolProp as CP
from Ref_Safety import *  # importing the function from the other file
from Ref_Cycle import *  # importing the function from the other file


class RefrigerantDiagramApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Refrigerant Diagrams")

        # Create a frame for the buttons
        self.button_frame = ttk.Frame(self.root)
        self.button_frame.pack(pady=10)

        # Create buttons for common refrigerants
        common_refrigerants = ['Water', 'R134a', 'R245fa', 'R1234ze(E)', 'Butane', 'Ammonia', 'IsoButane', 'Isopentane']
        self.buttons = []
        for refrigerant in common_refrigerants:
            button = ttk.Button(self.button_frame, text=refrigerant, command=lambda ref=refrigerant: self.plot_diagrams(ref))
            button.grid(row=2, column=common_refrigerants.index(refrigerant), padx=5, pady=5)
            self.buttons.append(button)

        # Create a dropdown menu for less common refrigerants
        self.refrigerant_var = tk.StringVar()
        self.refrigerant_var.set("Select refrigerant")
        self.refrigerant_combobox = ttk.Combobox(self.button_frame, textvariable=self.refrigerant_var)
        self.refrigerant_combobox.grid(row=3, column=0, columnspan=2, padx=5, pady=5)

        # List of less common refrigerants
        self.less_common_refrigerants = ['1-Butene', 'Acetone', 'Air', 'Ammonia', 'Argon', 'Benzene', 'CarbonDioxide',
                                         'CarbonMonoxide', 'CarbonylSulfide', 'cis-2-Butene', 'CycloHexane', 'Cyclopentane',
                                         'CycloPropane', 'D4', 'D5', 'D6', 'Deuterium', 'Dichloroethane', 'DiethylEther',
                                         'DimethylCarbonate', 'DimethylEther', 'Ethane', 'Ethanol', 'EthylBenzene', 'Ethylene',
                                         'EthyleneOxide', 'Fluorine', 'HeavyWater', 'Helium', 'HFE143m', 'Hydrogen',
                                         'HydrogenChloride', 'HydrogenSulfide', 'IsoButane', 'IsoButene', 'Isohexane',
                                         'Isopentane', 'Krypton', 'm-Xylene', 'MD2M', 'MD3M', 'MD4M', 'MDM', 'Methane',
                                         'Methanol', 'MethylLinoleate', 'MethylLinolenate', 'MethylOleate', 'MethylPalmitate',
                                         'MethylStearate', 'MM', 'n-Butane', 'n-Decane', 'n-Dodecane', 'n-Heptane', 'n-Hexane',
                                         'n-Nonane', 'n-Octane', 'n-Pentane', 'n-Propane', 'n-Undecane', 'Neon', 'Neopentane',
                                         'Nitrogen', 'NitrousOxide', 'Novec649', 'o-Xylene', 'OrthoDeuterium', 'OrthoHydrogen',
                                         'Oxygen', 'p-Xylene', 'ParaDeuterium', 'ParaHydrogen', 'Propylene', 'Propyne', 'R11',
                                         'R113', 'R114', 'R115', 'R116', 'R12', 'R123', 'R1233zd(E)', 'R1234yf', 'R1234ze(E)',
                                         'R1234ze(Z)', 'R124', 'R1243zf', 'R125', 'R13', 'R134a', 'R13I1', 'R14', 'R141b', 'R142b',
                                         'R143a', 'R152A', 'R161', 'R21', 'R218', 'R22', 'R227EA', 'R23', 'R236EA', 'R236FA',
                                         'R245ca', 'R245fa', 'R32', 'R365MFC', 'R40', 'R404A', 'R407C', 'R41', 'R410A', 'R507A',
                                         'RC318', 'SES36', 'SulfurDioxide', 'SulfurHexafluoride', 'Toluene', 'trans-2-Butene', 'Water',
                                         'Xenon']

        # Set options for the dropdown menu
        self.refrigerant_combobox['values'] = self.less_common_refrigerants

        # Add a plot button
        self.plot_button = ttk.Button(self.button_frame, text="Plot", command=self.plot_selected_refrigerant)
        self.plot_button.grid(row=3, column=2, padx=5, pady=5)

        # Create a canvas for plotting
        self.fig, self.ax = plt.subplots(1, 2, figsize=(12, 5))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        #create a frame for temperature fields
        self.input_frame = ttk.Frame(self.root)
        self.input_frame.pack(pady=10)
        
        # Create entry fields for evaporator temperatures
        self.evap_temp_label = ttk.Label(self.input_frame, text="Evaporator Temp (°C):")
        self.evap_temp_label.grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.evap_temp_entry = ttk.Entry(self.input_frame)
        #placeholder for temperature
        self.evap_temp_entry.insert(25, '60')
        self.evap_temp_entry.grid(row=0, column=1, padx=5, pady=5)

        # Create entry fields for evaporator temperatures
        self.cond_temp_label = ttk.Label(self.input_frame, text="Condenser Temp (°C):")
        self.cond_temp_label.grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.cond_temp_entry = ttk.Entry(self.input_frame)
        #placeholder for temperature
        self.cond_temp_entry.insert(100, '100')
        self.cond_temp_entry.grid(row=1, column=1, padx=5, pady=5)
        
        #create entry field for compressor power
        self.comp_power_label = ttk.Label(self.input_frame, text="Compressor Power (kW):")
        self.comp_power_label.grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.comp_power_entry = ttk.Entry(self.input_frame)
        #placeholder for power
        self.comp_power_entry.insert(80, '40')
        self.comp_power_entry.grid(row=2, column=1, padx=5, pady=5)
        

        # Create frames for environmental and health ratings
        self.env_frame = ttk.Frame(self.root)
        self.env_frame.pack(pady=10)

        self.health_frame = ttk.Frame(self.root)
        self.health_frame.pack(pady=10)

        # Labels for environmental and health ratings
        self.env_label = ttk.Label(self.env_frame, text="Environmental Ratings:")
        self.env_label.pack()

        self.health_label = ttk.Label(self.health_frame, text="Health Ratings:")
        self.health_label.pack()

    def plot_heat_pump_cycle(self, refrigerant, t_evap, t_cond, comp_power):
        # get the values of the heat pump cycle
        p_evap, p_cond, t_1, p_1, h_1, s_1, s_2, t_2, p_2, h_2,s_2x, t_2x, p_2x, h_2x, h_3, s_3, t_3, p_3, h_4, p_4, t_4, s_4, COP, ref_flowrate, heat_load, cooling_load, temp_lift = get_refrigeration_cycle(refrigerant, t_evap, t_cond, comp_power)

        # Plot heat pump cycle on P-H diagram
        self.ax[0].plot([h_1, h_2, h_2x, h_3, h_4, h_1],
                        [p_1, p_2, p_2x, p_3, p_4, p_1],
                        'g-', label='Heat Pump Cycle')

        # Add arrows to indicate direction of the cycle
        self.ax[0].annotate("", xy=(h_2, p_2), xytext=(h_1, p_1),
                            arrowprops=dict(arrowstyle="->", connectionstyle="arc3", color="g"))

        # Add annotations for each point
        self.ax[0].text(h_1, p_1, "1", fontsize=12, ha='right')
        self.ax[0].text(h_2, p_2, "2", fontsize=12, ha='right')
        self.ax[0].text(h_2x, p_2x, "2x", fontsize=12, ha='right')
        self.ax[0].text(h_3, p_3, "3", fontsize=12, ha='left')
        self.ax[0].text(h_4, p_4, "4", fontsize=12, ha='left')

        # Plot heat pump cycle on T-S diagram
        self.ax[1].plot([s_1, s_2, s_2x, s_3, s_4, s_1],
                        [t_1, t_2, t_2x, t_3, t_4, t_1],
                        'g-', label='Heat Pump Cycle')

        # Add arrows to indicate direction of the cycle
        self.ax[1].annotate("", xy=(s_2, t_2), xytext=(s_1, t_1),
                            arrowprops=dict(arrowstyle="->", connectionstyle="arc3", color="g"))

        # Add annotations for each point in T-S diagram
        self.ax[1].text(s_1, t_1, "1", fontsize=12, ha='right')
        self.ax[1].text(s_2, t_2, "2", fontsize=12, ha='right')
        self.ax[1].text(s_2x, t_2x, "2x",fontsize=12, ha='right')
        self.ax[1].text(s_3, t_3, "3", fontsize=12, ha='left')
        self.ax[1].text(s_4, t_4, "4", fontsize=12, ha='left')
        
        #Display Key Outputs
        self.ref_flowrate_label = ttk.Label(self.input_frame, text=f"Refrigerant Flow Rate: {round(ref_flowrate,4)} kg/s", foreground='green')
        self.ref_flowrate_label.grid(row=3, column=0, columnspan=2, padx=5, pady=5)
        self.COP_label = ttk.Label(self.input_frame, text=f"COP: {round(COP, 2)}", foreground='green')
        self.COP_label.grid(row=4, column=0, columnspan=2, padx=5, pady=5)
        self.Heat_load_label = ttk.Label(self.input_frame, text=f"Heat Load: {round(heat_load, 2)} kW", foreground='red')
        self.Heat_load_label.grid(row=5, column=0, columnspan=2, padx=5, pady=5)
        self.Cooling_load_label = ttk.Label(self.input_frame, text=f"Cooling Load: {round(cooling_load, 2)} kW", foreground='blue')
        self.Cooling_load_label.grid(row=6, column=0, columnspan=2, padx=5, pady=5)
        self.Temp_lift_label = ttk.Label(self.input_frame, text=f"Temperature Lift: {round(temp_lift, 2)} K", foreground='green')
        self.Temp_lift_label.grid(row=7, column=0, columnspan=2, padx=5, pady=5)

        # Draw canvas
        self.canvas.draw()

    def plot_diagrams(self, refrigerant):
        # Get the values from the entry fields
        evap_temp_str = self.evap_temp_entry.get()
        cond_temp_str = self.cond_temp_entry.get()
        comp_power_str = self.comp_power_entry.get()

        # Check if both entry fields are not empty
        if evap_temp_str and cond_temp_str:
            try:
                # Convert the string values to floats
                t_evap = float(evap_temp_str)
                t_cond = float(cond_temp_str)
                comp_power = float(comp_power_str)
            except ValueError:
                # Handle the case where the strings cannot be converted to floats
                # Display an error message or take appropriate action
                print("Error: Invalid temperature or power values.")
                return
        else:
            # Handle the case where one or both entry fields are empty
            # Display an error message or take appropriate action
            print("Error: Evaporator and condenser temperatures are required.")
            return

        # Define temperature range for the plot
        Tmin = CP.PropsSI(refrigerant, 'Tmin')
        Tmax = CP.PropsSI(refrigerant, 'Tcrit')
        T = [Tmin + i * (Tmax - Tmin) / 100 for i in range(101)]

        # Calculate properties for P-H diagram
        p_sat = [CP.PropsSI('P', 'T', T[i], 'Q', 0, refrigerant) / 1000 for i in range(101)]
        h_sat_v = [CP.PropsSI('H', 'T', T[i], 'Q', 1, refrigerant) / 1000 for i in range(101)]
        h_sat_l = [CP.PropsSI('H', 'T', T[i], 'Q', 0, refrigerant) / 1000 for i in range(101)]

        env_data = get_environmental_ratings(refrigerant)
        health_data = get_health_ratings(refrigerant)

        # Plot P-H diagram
        self.ax[0].clear()
        self.ax[0].plot(h_sat_v, p_sat, 'r-', label='Saturated Vapor')
        self.ax[0].plot(h_sat_l, p_sat, 'b-', label='Saturated Liquid')
        self.ax[0].set_xlabel('Enthalpy (kJ/kg)')
        self.ax[0].set_ylabel('Pressure (kPa)')
        self.ax[0].set_title('P-H Diagram for ' + refrigerant)
        self.ax[0].legend()
        self.ax[0].grid()

        # Calculate properties for T-S diagram
        s_sat_v = [CP.PropsSI('S', 'T', T[i], 'Q', 1, refrigerant) / 1000 for i in range(101)]
        s_sat_l = [CP.PropsSI('S', 'T', T[i], 'Q', 0, refrigerant) / 1000 for i in range(101)]

        # Plot T-S diagram
        self.ax[1].clear()
        self.ax[1].plot(s_sat_v, T, 'r-', label='Saturated Vapor')
        self.ax[1].plot(s_sat_l, T, 'b-', label='Saturated Liquid')
        self.ax[1].set_xlabel('Entropy (kJ/(kg*K))')
        self.ax[1].set_ylabel('Temperature (K)')
        self.ax[1].set_title('T-S Diagram for ' + refrigerant)
        self.ax[1].legend()
        self.ax[1].grid()

        # Plot heat pump cycle
        self.plot_heat_pump_cycle(refrigerant, t_evap, t_cond, comp_power)

        # Draw canvas
        self.canvas.draw()    
        

        # Display environmental and health ratings
        self.env_label.config(text=f"Environmental Ratings: {env_data}")
        self.health_label.config(text=f"Health Ratings: {health_data}")

    def plot_selected_refrigerant(self):
        selected_refrigerant = self.refrigerant_var.get()
        if selected_refrigerant:
            self.plot_diagrams(selected_refrigerant)


def main():
    root = tk.Tk()
    app = RefrigerantDiagramApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
