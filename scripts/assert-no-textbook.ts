import { readdirSync, readFileSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join, resolve } from "node:path";

export const BANNED_IDENTIFIERS = [
  "vocabulary_score",
  "grammar_lesson_id",
  "textbook_percent",
  "translation_vi",
  "translation_en",
  "flashcard_deck",
  "srs_interval",
];
const SCAN_ROOTS = [
  "apps",
  "packages",
  "scripts",
  "docs/sad/03-design/openapi.yaml",
];
const SKIP_DIRS = new Set([
  "node_modules",
  ".next",
  "test",
  "tests",
  "__tests__",
  ".venv",
  "__pycache__",
  "ios",
  "android",
]);
const EXTENSIONS = /\.(ts|tsx|js|mjs|py|pyi|sql|yaml|yml|json)$/i;
const GUARD_FILE = resolve(fileURLToPath(import.meta.url));

export function walk(dir: string, acc: string[] = []): string[] {
  const info = statSync(dir, { throwIfNoEntry: false });
  if (!info) return acc;
  if (info.isFile()) {
    if (EXTENSIONS.test(dir)) acc.push(dir);
    return acc;
  }
  for (const name of readdirSync(dir)) {
    if (SKIP_DIRS.has(name)) continue;
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, acc);
    else if (EXTENSIONS.test(name)) acc.push(p);
  }
  return acc;
}

export function findHits(files: readonly string[]): string[] {
  const hits: string[] = [];
  for (const file of files) {
    const text = readFileSync(file, "utf8").toLowerCase();
    for (const identifier of BANNED_IDENTIFIERS) {
      if (text.includes(identifier.toLowerCase())) {
        hits.push(`${file}: ${identifier}`);
      }
    }
  }
  return hits;
}

export function run(cwd = process.cwd()): string[] {
  const files = SCAN_ROOTS.flatMap((root) => walk(resolve(cwd, root)))
    .filter((file) => resolve(file) !== GUARD_FILE);
  return findHits(files);
}

const isCli = process.argv[1] && resolve(process.argv[1]) === GUARD_FILE;
if (isCli) {
  const hits = run();
  if (hits.length) {
    console.error(hits.join("\n"));
    process.exit(1);
  }
}
