module.exports = {
  preset: "ts-jest",
  testEnvironment: "node",
  globalSetup: "<rootDir>/test/global-setup.cjs",
  globalTeardown: "<rootDir>/test/global-teardown.cjs",
  setupFiles: ["<rootDir>/test/test-env.cjs"],
  testMatch: ["<rootDir>/test/**/*.spec.ts", "<rootDir>/test/**/*.e2e-spec.ts"],
  forceExit: true,
};
