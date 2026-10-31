import CoolProp.CoolProp as CP

def get_refrigeration_cycle( refrigerant, t_evap, t_cond, comp_power):
    
    t_evap = t_evap + 273.15
    t_cond = t_cond + 273.15
    
    try:
        p_evap = CP.PropsSI('P', 'T', t_evap, 'Q', 0, refrigerant) 
        p_cond = CP.PropsSI('P', 'T', t_cond, 'Q', 0, refrigerant)
        t_1 = t_evap
        p_1 = p_evap
        h_1 = CP.PropsSI('H', 'P', p_evap, 'Q', 1, refrigerant)
        s_1 = CP.PropsSI('S', 'P', p_evap, 'Q', 1, refrigerant)

        s_2 = s_1 + 100
        p_2 = p_cond
        h_2 = CP.PropsSI('H', 'S', s_2, 'P', p_cond, refrigerant)
        t_2 = CP.PropsSI('T', 'P', p_cond, 'S', s_2, refrigerant)
        
        p_2x =p_2
        h_2x = CP.PropsSI('H', 'P', p_2x, 'Q', 1, refrigerant)
        s_2x = CP.PropsSI('S', 'P', p_2x, 'Q', 1, refrigerant)
        t_2x = CP.PropsSI('T', 'P', p_2x, 'Q', 1, refrigerant)

        h_3 = CP.PropsSI('H', 'P', p_cond, 'Q', 0, refrigerant)
        s_3 = CP.PropsSI('S', 'P', p_cond, 'Q', 0, refrigerant)
        t_3 = t_cond
        p_3 = p_cond

        h_4 = h_3
        q_4 = CP.PropsSI('Q', 'P', p_cond, 'H', h_4, refrigerant) 
        p_4 = p_evap
        t_4 = t_evap
        s_4 = CP.PropsSI('S', 'P', p_evap, 'Q', q_4, refrigerant)
        
        
        p_1 = p_1 / 1000
        p_2 = p_2 / 1000
        p_2x = p_2x / 1000
        p_3 = p_3 / 1000
        p_4 = p_4 / 1000
        h_1 = h_1 / 1000
        h_2 = h_2 / 1000
        h_2x = h_2x / 1000
        h_3 = h_3 / 1000
        h_4 = h_4 / 1000
        s_1 = s_1 / 1000
        s_2 = s_2 / 1000
        s_2x = s_2x / 1000
        s_3 = s_3 / 1000
        s_4 = s_4 / 1000
        
        COP= (h_2-h_3)/(h_2-h_1)
        rdot = comp_power / (h_2 - h_1) #kg/s
        heat_load = rdot *(h_2 - h_3) #kW
        cooling_load = rdot *(h_1 - h_4) #kW
        temp_lift = t_cond - t_evap #K

        return p_evap, p_cond, t_1, p_1, h_1, s_1, s_2, t_2, p_2, h_2,s_2x, t_2x, p_2x, h_2x, h_3, s_3, t_3, p_3, h_4, p_4, t_4, s_4, COP, rdot, heat_load, cooling_load, temp_lift
    except ValueError as err:
        raise ValueError(
            f"Refrigeration cycle for {refrigerant} not solvable at "
            f"T_evap={t_evap - 273.15:.1f} °C, T_cond={t_cond - 273.15:.1f} °C: {err}"
        ) from err

# refrigerant = 'IsoButane'
# p_evap, p_cond, t_1, p_1, h_1, s_1, s_2, t_2, p_2, h_2,s_2x, t_2x, p_2x, h_2x, h_3, s_3, t_3, p_3, h_4, p_4, t_4, s_4, COP, rdot, heat_load, cooling_load, temp_lift = get_refrigeration_cycle(refrigerant,25,90, 80)
# print(f'Pressure at Evaporator: {round(p_evap, 2)} Pa')
# print(f'Pressure at Condenser: {round(p_cond, 2)} Pa')
# print(f'Temperature at Evaporator: {round(t_1 - 273.15, 2)} degrees Celsius')
# print(f'Pressure at Evaporator: {round(p_1, 2)} Pa')
# print(f'Enthalpy at Evaporator: {round(h_1, 2)} J/kg')
# print(f'Entropy at Evaporator: {round(s_1, 2)} J/(kg·K)')
# print(f'Entropy at Condenser: {round(s_2, 2)} J/(kg·K)')
# print(f'Temperature at Condenser: {round(t_2 - 273.15, 2)} degrees Celsius')
# print(f'Pressure at Condenser: {round(p_2, 2)} Pa')
# print(f'Enthalpy at Condenser: {round(h_2, 2)} J/kg')
# print(f'Enthalpy at Condenser: {round(h_3, 2)} J/kg')
# print(f'Entropy at Condenser: {round(s_3, 2)} J/(kg·K)')
# print(f'Temperature at Condenser: {round(t_3 - 273.15, 2)} degrees Celsius')
# print(f'Pressure at Condenser: {round(p_3, 2)} Pa') 
# print(f'Enthalpy at Condenser: {round(h_4, 2)} J/kg')
# print(f'Pressure at Condenser: {round(p_4, 2)} Pa')
# print(f'Temperature at Condenser: {round(t_4 - 273.15, 2)} degrees Celsius')
# print(f'Entropy at Condenser: {round(s_4, 2)} J/(kg·K)')
# print(f'COP: {round(COP, 2)}')

