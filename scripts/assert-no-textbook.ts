import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const banned = [
  "vocabulary_score",
  "grammar_lesson_id",
  "textbook_percent",
  "translation_vi",
];
const roots = ["apps", "packages"];

function walk(dir: string, acc: string[] = []): string[] {
  if (!statSync(dir, { throwIfNoEntry: false })) return acc;
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name === ".next" || name === "test" || name === "__tests__") continue;
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, acc);
    else if (/\.(ts|tsx|prisma|sql)$/.test(name)) acc.push(p);
  }
  return acc;
}

const hits: string[] = [];
for (const root of roots) {
  for (const file of walk(root)) {
    const text = readFileSync(file, "utf8");
    for (const b of banned) {
      if (text.includes(b)) hits.push(`${file}: ${b}`);
    }
  }
}
if (hits.length) {
  console.error(hits.join("\n"));
  process.exit(1);
}
