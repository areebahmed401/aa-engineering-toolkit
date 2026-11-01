import { describe, expect, it } from "vitest";
import type { ResultField } from "./types";
import { vesselReportSections, withUnit } from "./vessel";

const f = (name: string, value: unknown): ResultField => ({ name, label: name, unit: "", summary: false, value });

describe("vessel helpers", () => {
  it("shows thickness in mm / in and pressure in MPa / psi", () => {
    expect(withUnit(0.01, "m", "SI")).toBe("10 mm");
    expect(withUnit(0.0254, "m", "Imperial")).toBe("1 in");
    expect(withUnit(1.5e6, "Pa", "SI")).toBe("1.5 MPa");
    expect(withUnit(6894.757293168 * 100, "Pa", "Imperial")).toBe("100 psi");
  });

  it("writes the checks table, notes and disclaimer", () => {
    const md = vesselReportSections(
      [
        f("checks", [{ item: "Shell thickness", clause: "UG-27(c)(1)", required: 0.008, provided: 0.01, unit: "m", status: "PASS" }]),
        f("notes", ["Supports not checked"]),
        f("disclaimer", "Verify against the current code edition"),
      ],
      "SI",
    );
    expect(md).toContain("| Shell thickness | UG-27(c)(1) | 8 mm | 10 mm | PASS |");
    expect(md).toContain("- Supports not checked");
    expect(md).toContain("> Verify against the current code edition");
  });
});
