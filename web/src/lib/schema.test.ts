import { describe, expect, it } from "vitest";
import { needsFluidLibrary } from "./fluids";
import { checkBounds, defaultValues, fieldsFromSchema } from "./schema";
import type { JsonSchema } from "./types";
import { decodeInputs, encodeInputs } from "./urlState";

// Shape of a pydantic v2 schema like engtoolkit's BeamAnalysisInputs
const schema: JsonSchema = {
  $defs: {
    SectionInputs: {
      title: "SectionInputs",
      properties: {
        shape: { enum: ["rectangle", "i_beam"], type: "string", default: "i_beam", label: "Section shape" },
        width: { type: "number", default: 0.1, exclusiveMinimum: 0, unit: "m", label: "Width" },
      },
    },
    LoadInput: {
      title: "LoadInput",
      properties: {
        value: { type: "number", default: 10000, label: "Value" },
        x_end: { anyOf: [{ type: "number" }, { type: "null" }], default: null, unit: "m", label: "UDL end" },
      },
    },
  },
  properties: {
    section: { $ref: "#/$defs/SectionInputs" },
    length: { type: "number", default: 2, exclusiveMinimum: 0, unit: "m", label: "Span" },
    dn: { enum: [15, 50, 100], type: "integer", default: 50, label: "DN" },
    loads: { type: "array", items: { $ref: "#/$defs/LoadInput" } },
  },
};

describe("schema to form fields", () => {
  const fields = fieldsFromSchema(schema);

  it("resolves nested models, enums, arrays and nullable numbers", () => {
    const byName = Object.fromEntries(fields.map((f) => [f.name, f]));
    expect(byName.section.kind).toBe("object");
    expect(byName.section.label).toBe("Section"); // not the class name
    expect(byName.section.fields?.map((f) => f.name)).toEqual(["shape", "width"]);
    expect(byName.dn.kind).toBe("enum");
    expect(byName.dn.options).toEqual([15, 50, 100]);
    expect(byName.loads.kind).toBe("array");
    expect(byName.loads.item?.fields?.find((f) => f.name === "x_end")?.nullable).toBe(true);
    expect(byName.length.unit).toBe("m");
  });

  it("builds defaults recursively", () => {
    expect(defaultValues(fields)).toEqual({
      section: { shape: "i_beam", width: 0.1 },
      length: 2,
      dn: 50,
      loads: [{ value: 10000, x_end: null }],
    });
  });

  it("checks bounds", () => {
    const length = fields.find((f) => f.name === "length")!;
    expect(checkBounds(length, 0)).toBe("Must be > 0");
    expect(checkBounds(length, 1)).toBeNull();
  });
});

describe("shareable links", () => {
  it("encodes only changed values and decodes them back", () => {
    const defaults = { a: 1, b: { c: 2 } };
    const values = { a: 1, b: { c: 3 } };
    const encoded = encodeInputs(values, defaults);
    expect(encoded).not.toContain("=");
    expect(decodeInputs(encoded)).toEqual({ b: { c: 3 } });
    expect(encodeInputs(defaults, defaults)).toBe("");
  });

  it("ignores broken links", () => {
    expect(decodeInputs("not-base64!!")).toEqual({});
    expect(decodeInputs(null)).toEqual({});
  });
});

describe("fluid library hint", () => {
  it("matches the Python rule", () => {
    expect(needsFluidLibrary("Water")).toBe(true);
    expect(needsFluidLibrary("R134a")).toBe(true);
    expect(needsFluidLibrary("HEOS::Air")).toBe(true);
    expect(needsFluidLibrary("IF97::Water")).toBe(false);
    expect(needsFluidLibrary("INCOMP::MEG[0.3]")).toBe(false);
    expect(needsFluidLibrary("Air (1 atm table)")).toBe(false);
  });
});
