import { readFileSync } from "node:fs";
import { join } from "node:path";

test("FR-NEG-004 prisma has no textbook progress columns", () => {
  const schema = readFileSync(join(__dirname, "../prisma/schema.prisma"), "utf8");
  expect(schema).not.toMatch(/vocabulary_score|grammar_lesson_id|textbook_percent|translation_vi/);
  expect(schema).not.toMatch(/model ComprehensionProbe/);
  expect(schema).toMatch(/minutesComprehensible/);
  expect(schema).toMatch(/currentCiLevel/);
});
