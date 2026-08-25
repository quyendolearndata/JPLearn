const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");

const statePath = path.join(os.tmpdir(), "jplearn-jest-postgres.json");

module.exports = async () => {
  let state;
  try {
    state = JSON.parse(await fs.readFile(statePath, "utf8"));
  } catch {
    return;
  }

  try {
    process.kill(state.pid, "SIGTERM");
  } catch (error) {
    if (error.code !== "ESRCH") throw error;
  }

  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      process.kill(state.pid, 0);
      await new Promise((resolve) => setTimeout(resolve, 100));
    } catch (error) {
      if (error.code === "ESRCH") break;
      throw error;
    }
  }
  try {
    process.kill(state.pid, "SIGKILL");
  } catch (error) {
    if (error.code !== "ESRCH") throw error;
  }
  await fs.rm(state.databaseDir, { recursive: true, force: true });
  await fs.rm(statePath, { force: true });
};
