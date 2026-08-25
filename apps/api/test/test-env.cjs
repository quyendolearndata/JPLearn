const { readFileSync } = require("node:fs");
const { tmpdir } = require("node:os");
const { join } = require("node:path");

const statePath = join(tmpdir(), "jplearn-jest-postgres.json");
const { databaseUrl } = JSON.parse(readFileSync(statePath, "utf8"));
process.env.DATABASE_URL = databaseUrl;
process.env.JWT_SECRET = "test-secret";
process.env.API_PUBLIC_URL = "http://localhost:3001";
