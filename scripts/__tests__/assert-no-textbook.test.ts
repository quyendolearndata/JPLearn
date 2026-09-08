import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import assert from "node:assert/strict";

import { findHits } from "../assert-no-textbook.ts";

test("findHits detects banned identifiers case-insensitively", () => {
  const directory = mkdtempSync(join(tmpdir(), "jplearn-guard-"));
  const file = join(directory, "fixture.ts");
  writeFileSync(file, "const score = VOCABULARY_SCORE;\n");

  assert.deepEqual(findHits([file]), [`${file}: vocabulary_score`]);
});

test("findHits returns no hits for a clean file", () => {
  const directory = mkdtempSync(join(tmpdir(), "jplearn-guard-"));
  const file = join(directory, "fixture.ts");
  writeFileSync(file, "const message = 'context first';\n");

  assert.deepEqual(findHits([file]), []);
});
