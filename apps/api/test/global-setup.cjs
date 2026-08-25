const { execFileSync } = require("node:child_process");
const { existsSync } = require("node:fs");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");

const statePath = path.join(os.tmpdir(), "jplearn-jest-postgres.json");
const port = 55000 + (process.pid % 1000);
const databaseDir = path.join(os.tmpdir(), `jplearn-jest-postgres-${port}`);

async function killPrevious() {
  try {
    const previous = JSON.parse(await fs.readFile(statePath, "utf8"));
    try {
      process.kill(previous.pid, "SIGKILL");
    } catch (error) {
      if (error.code !== "ESRCH") throw error;
    }
    await new Promise((resolve) => setTimeout(resolve, 400));
  } catch {
    // no previous run
  }
}

module.exports = async () => {
  try {
    process.env.JWT_SECRET = "test-secret";
    process.env.API_PUBLIC_URL = "http://localhost:3001";
    await killPrevious();

    const { default: EmbeddedPostgres } = await import("embedded-postgres");
    const postgres = new EmbeddedPostgres({
      databaseDir,
      port,
      user: "postgres",
      password: "postgres",
      persistent: true,
      initdbFlags: ["--set=shared_memory_type=mmap"],
      postgresFlags: [
        "-h",
        "127.0.0.1",
        "-c",
        "shared_memory_type=mmap",
      ],
      onLog: () => undefined,
      onError: () => undefined,
    });

    if (!existsSync(path.join(databaseDir, "PG_VERSION"))) {
      await postgres.initialise();
    }
    try {
      await postgres.start();
    } catch (startError) {
      await fs.rm(databaseDir, { recursive: true, force: true });
      await postgres.initialise();
      await postgres.start();
      void startError;
    }
    await postgres.createDatabase("jplearn_test").catch((error) => {
      if (!String(error?.message).includes("already exists")) throw error;
    });

    const databaseUrl =
      `postgresql://postgres:postgres@127.0.0.1:${port}/jplearn_test`;
    process.env.DATABASE_URL = databaseUrl;
    execFileSync(path.resolve(__dirname, "../node_modules/.bin/prisma"), [
      "migrate",
      "deploy",
      "--schema",
      path.resolve(__dirname, "../prisma/schema.prisma"),
    ], {
      env: process.env,
      stdio: "ignore",
    });

    await fs.writeFile(statePath, JSON.stringify({
      databaseDir,
      databaseUrl,
      pid: Number((await fs.readFile(path.join(databaseDir, "postmaster.pid"), "utf8"))
        .split("\n")[0]),
    }));
  } catch (error) {
    console.error("globalSetup failed:", error);
    throw error;
  }
};
