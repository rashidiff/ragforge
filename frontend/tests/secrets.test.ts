import { expect, it } from "vitest";
import { containsPotentialSecret } from "../src/lib/secrets";

it("recognizes common provider credential shapes without changing input", () => {
  expect(containsPotentialSecret(`sk-proj-${"a".repeat(28)}`)).toBe(true);
  expect(containsPotentialSecret(`AIza${"A".repeat(32)}`)).toBe(true);
  expect(containsPotentialSecret("A normal question about an API key" )).toBe(false);
});
