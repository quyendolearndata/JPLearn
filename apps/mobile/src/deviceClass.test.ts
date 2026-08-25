import { deviceClassFrom } from "./deviceClass";

test("NFR-XPLAT-002 ipad vs phone", () => {
  expect(deviceClassFrom({ os: "ios", width: 390, height: 844 })).toBe("phone");
  expect(deviceClassFrom({ os: "ios", width: 1024, height: 1366 })).toBe("ipad");
  expect(deviceClassFrom({ os: "android", width: 1024, height: 1366 })).toBe("phone");
});
