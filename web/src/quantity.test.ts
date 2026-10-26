import { describe, expect, it } from "vitest";
import { formatQuantity, scaleLine } from "./quantity";
import { expandTemplate, fillFirstBlank, suggest } from "./templates";

describe("quantities", () => {
  it("formats fractions", () => {
    expect(formatQuantity(1.5)).toBe("1 1/2");
    expect(formatQuantity(1 / 3)).toBe("1/3");
    expect(formatQuantity(2)).toBe("2");
  });
  it("scales lines", () => {
    const line = { raw_text: "1/2 cup flour (sifted)", quantity: 0.5, unit: "cup", name: "flour", note: "sifted" };
    expect(scaleLine(line, 2)).toBe("1 cup flour, sifted");
    expect(scaleLine(line, 1)).toBe("1/2 cup flour (sifted)");
    expect(scaleLine(line, 4)).toBe("2 cups flour, sifted");
    expect(scaleLine({ raw_text: "salt to taste", name: "salt" }, 2)).toBe("salt to taste");
  });
});

describe("templates", () => {
  const templates = [
    { group: "Prep", text: "Preheat oven to {temp}.", custom: false },
    { group: "Cooking", text: "Bake at {temp} for {time}, or until {doneness}.", custom: false },
    { group: "Mine", text: "Bake with love.", custom: true },
  ];
  it("suggests by prefix and by words", () => {
    expect(suggest("pre", templates).map((t) => t.text)).toEqual(["Preheat oven to {temp}."]);
    expect(suggest("bake", templates)[0].text).toBe("Bake with love.");
    expect(suggest("until", templates).map((t) => t.text)).toEqual([templates[1].text]);
    expect(suggest("p", templates)).toEqual([]);
  });
  it("expands and fills blanks", () => {
    const { text, slots } = expandTemplate(templates[1].text);
    expect(slots).toEqual(["temp", "time", "doneness"]);
    expect(fillFirstBlank(text, "350°F")).toBe("Bake at 350°F for ___, or until ___.");
  });
});
