"""
Precompute the PyBaMM reference grid the web app plots next to the equivalent-circuit and aging models.

    pip install -e ".[battery]"
    python scripts/generate_battery_reference.py            # full grid, about 10 min on 4 cores
    python scripts/generate_battery_reference.py --quick    # small grid for testing, about 1 min

Writes src/engtoolkit/electrical/data/pybamm_reference.json (committed, ~50 kB) with, for the LG M50 cell:
- OCV-SOC table (Chen2020 electrode OCPs) and 2RC parameters fitted to DFN pulses at 10/25/40 °C
  (copied into catalogs/data/cells.yaml),
- DFN + lumped thermal discharge curves for C-rate × ambient temperature,
- SPM + SEI + lithium plating (OKane2022) capacity fade over cycles for C-rate × ambient temperature.
The thermal mass and cooling area of the PyBaMM runs match the catalog cell (mass × cp, surface area).
"""
from __future__ import annotations

import argparse
import json
import math
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "engtoolkit" / "electrical" / "data" / "pybamm_reference.json"
CELL = "LG M50 21700 (NMC811)"
H_NATURAL = 10.0  # W/(m²·K), still air incl. radiation (as PyBaMM's default)
SOC_GRID = [0.0, 0.01, 0.02, 0.03, 0.05, 0.075, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65,
            0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 0.98, 1.0]


def _round(obj, sig: int = 5):
    if isinstance(obj, dict):
        return {k: _round(v, sig) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_round(v, sig) for v in obj]
    if isinstance(obj, np.ndarray):
        return _round(obj.tolist(), sig)
    if isinstance(obj, (float, np.floating)):
        v = float(obj)
        return v if v == 0 or not math.isfinite(v) else float(f"{v:.{sig}g}")
    return obj


def _cell_thermal():
    from engtoolkit.catalogs import get_cell
    cell = get_cell(CELL)
    return cell.mass * cell.cp, cell.surface_area


def _discharge(args):
    from engtoolkit.electrical.battery import pybamm_models as pm
    c_rate, T = args
    C_th, area = _cell_thermal()
    return pm.discharge(c_rate, T, H_NATURAL, heat_capacity=C_th, area=area)


def _degradation(args):
    from engtoolkit.electrical.battery import pybamm_models as pm
    c_rate, T, n_cycles, every = args
    C_th, area = _cell_thermal()
    t0 = time.perf_counter()
    out = pm.degradation(c_rate, T, n_cycles, H_NATURAL, save_every=every, heat_capacity=C_th, area=area)
    out["seconds"] = time.perf_counter() - t0
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quick", action="store_true", help="small grid (for testing the script)")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--cycles", type=int, default=500)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    import pybamm
    from engtoolkit.electrical.battery import pybamm_models as pm

    t_start = time.perf_counter()
    c_rates = [0.5, 1.0, 2.0]
    temps = [283.15, 298.15, 313.15]
    n_cycles = 20 if args.quick else args.cycles
    every = 5 if args.quick else 10
    if args.quick:
        temps = [298.15]

    print("OCV table and ECM fits...")
    ocv = pm.ocv_table(SOC_GRID)
    fits = [pm.fit_ecm(T) for T in (283.15, 298.15, 313.15)]
    # Arrhenius activation energy of the series resistance between 10 and 40 °C
    Ea = 8.314462618 * math.log(fits[0]["R0"] / fits[2]["R0"]) / (1 / 283.15 - 1 / 313.15)

    print("Discharge curves...")
    grid = [(c, T) for T in temps for c in c_rates]
    with ProcessPoolExecutor(args.workers) as pool:
        discharges = list(pool.map(_discharge, grid))
        print(f"Degradation runs ({n_cycles} cycles each)...")
        aging = list(pool.map(_degradation, [(c, T, n_cycles, every) for c, T in grid]))

    elapsed = time.perf_counter() - t_start
    data = {
        "meta": {
            "cell": CELL,
            "pybamm_version": pybamm.__version__,
            "generated": date.today().isoformat(),
            "generation_seconds": round(elapsed),
            "h": H_NATURAL,
            "heat_capacity": _cell_thermal()[0],
            "area": _cell_thermal()[1],
            "discharge_model": "DFN + lumped thermal, Chen2020 parameters (Chen et al. 2020)",
            "aging_model": "SPM + solvent-diffusion-limited SEI + partially reversible Li plating + lumped thermal, "
                           "OKane2022 parameters (O'Kane et al. 2022); discharge at C-rate to 2.5 V, "
                           "CC-CV charge at C/2 to 4.2 V (C/20 cut-off), 10 min rests",
        },
        "ocv": {"soc": SOC_GRID, "ocv": ocv},
        "ecm_fit": {"fits": fits, "Ea_R0": Ea},
        "discharge": discharges,
        "aging": aging,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(_round(data), separators=(",", ":")), encoding="utf-8")
    print(f"wrote {args.out} ({args.out.stat().st_size / 1e3:.0f} kB) in {elapsed / 60:.1f} min")

    f = fits[1]
    print("\ncells.yaml values for", CELL)
    print(f"    ecm: {{R0_mohm: {f['R0'] * 1e3:.2f}, R1_mohm: {f['R1'] * 1e3:.2f}, tau1_s: {f['tau1']:.1f}, "
          f"R2_mohm: {f['R2'] * 1e3:.2f}, tau2_s: {f['tau2']:.1f}, Ea_kJ_mol: {Ea / 1e3:.1f}, T_ref: 298.15}}")
    print("    ocv: " + ", ".join(f"[{s}, {v:.4f}]" for s, v in zip(SOC_GRID, ocv)))


if __name__ == "__main__":
    main()
