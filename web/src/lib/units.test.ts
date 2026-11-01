import { describe, expect, it } from "vitest";
import { displayUnit, formatNumber, inputString, toDisplay, toSI } from "./units";

describe("unit conversion", () => {
  it("converts absolute temperature with an offset", () => {
    expect(toDisplay(373.15, "K", "SI")).toBeCloseTo(100);
    expect(toDisplay(373.15, "K", "Imperial")).toBeCloseTo(212);
    expect(toSI(32, "K", "Imperial")).toBeCloseTo(273.15);
  });

  it("converts temperature differences without an offset", () => {
    expect(toDisplay(10, "ΔK", "SI")).toBeCloseTo(10);
    expect(toDisplay(10, "ΔK", "Imperial")).toBeCloseTo(18);
    expect(displayUnit("ΔK", "Imperial")).toBe("Δ°F");
  });

  it("round-trips common engineering units", () => {
    for (const unit of ["Pa", "J/kg", "W", "W/m", "m", "kg/s", "N", "N·m", "m^4", "Pa·s"]) {
      for (const system of ["SI", "Imperial"] as const) {
        expect(toSI(toDisplay(1234.5, unit, system), unit, system)).toBeCloseTo(1234.5, 6);
      }
    }
  });

  it("uses engineering display units", () => {
    expect(toDisplay(101325, "Pa", "SI")).toBeCloseTo(101.325);
    expect(toDisplay(101325, "Pa", "Imperial")).toBeCloseTo(14.696, 3);
    expect(toDisplay(10e3, "N", "Imperial")).toBeCloseTo(2248.09, 1);
    expect(toDisplay(1e-6, "m^4", "SI")).toBeCloseTo(100); // cm⁴
  });

  it("passes unknown units through", () => {
    expect(toDisplay(5, "furlong", "Imperial")).toBe(5);
    expect(displayUnit("furlong", "SI")).toBe("furlong");
  });
});

describe("formatting", () => {
  it("formats to ~4 significant figures", () => {
    expect(formatNumber(0.0743895)).toBe("0.07439");
    expect(formatNumber(1028.49)).toBe("1028");
    expect(formatNumber(2.5e-6)).toBe("2.500e-6");
    expect(formatNumber(null)).toBe("—");
    expect(formatNumber(true)).toBe("yes");
    expect(formatNumber("text")).toBe("text");
  });

  it("shows input values in display units without float noise", () => {
    expect(inputString(453.15, "K", "SI")).toBe("180");
    expect(inputString(3e5, "Pa", "SI")).toBe("300");
  });

  it("shows battery units", () => {
    expect(displayUnit("Ah", "SI")).toBe("A·h");
    expect(toDisplay(0.0234, "ohm", "SI")).toBeCloseTo(23.4);
    expect(toDisplay(3600, "s", "SI")).toBeCloseTo(60);
    expect(toDisplay(5000, "J", "SI")).toBeCloseTo(5);
  });
});
