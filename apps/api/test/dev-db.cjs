// Embedded Postgres riêng cho web e2e (port 55444, db jplearn_web_e2e).
// Dùng khi DB dev (localhost:5432) không chạy: `node test/dev-db.cjs`, giữ process sống.
// Sau khi in E2E_DB_READY <url>: migrate deploy + seed đã chạy xong.
const { existsSync } = require("node:fs");
const { execFileSync } = require("node:child_process");
const os = require("node:os");
const path = require("node:path");

const port = 55444;
const databaseDir = path.join(os.tmpdir(), "jplearn-web-e2e-pg");
const databaseUrl = `postgresql://postgres:postgres@127.0.0.1:${port}/jplearn_web_e2e`;

(async () => {
  const { default: EmbeddedPostgres } = await import("embedded-postgres");
  const postgres = new EmbeddedPostgres({
    databaseDir,
    port,
    user: "postgres",
    password: "postgres",
    persistent: true,
    initdbFlags: ["--set=shared_memory_type=mmap"],
    postgresFlags: ["-h", "127.0.0.1", "-c", "shared_memory_type=mmap"],
    onLog: () => undefined,
    onError: () => undefined,
  });

  if (!existsSync(path.join(databaseDir, "PG_VERSION"))) {
    await postgres.initialise();
  }
  try {
    await postgres.start();
  } catch {
    await postgres.initialise();
    await postgres.start();
  }
  await postgres.createDatabase("jplearn_web_e2e").catch(() => {});

  const env = { ...process.env, DATABASE_URL: databaseUrl };
  const bin = (name) => path.resolve(__dirname, "../node_modules/.bin", name);
  execFileSync(bin("prisma"), ["migrate", "deploy", "--schema", path.resolve(__dirname, "../prisma/schema.prisma")], { env, stdio: "inherit" });
  execFileSync(bin("tsx"), ["prisma/seed.ts"], { env, stdio: "inherit", cwd: path.resolve(__dirname, "..") });

  console.log(`E2E_DB_READY ${databaseUrl}`);
  setInterval(() => undefined, 1000);
})().catch((error) => {
  console.error("dev-db failed:", error);
  process.exit(1);
});
