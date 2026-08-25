import { signMediaUrl, verifyMediaSig } from "../src/media/signed-url";

describe("signed media URL (FR-CMS-003, FR-CMS-004)", () => {
  const secret = "test-secret";
  const assetId = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";
  const nowSec = 1_700_000_000;

  it("builds a URL the player can fetch without Authorization", () => {
    const url = signMediaUrl({
      assetId,
      baseUrl: "http://localhost:3001",
      secret,
      nowSec,
      ttlSec: 60,
    });
    const parsed = new URL(url);
    expect(parsed.origin + parsed.pathname).toBe(
      "http://localhost:3001/media/" + assetId,
    );
    expect(parsed.searchParams.get("exp")).toBe("1700000060");
    expect(parsed.searchParams.get("sig")).toMatch(/^[a-f0-9]{64}$/);
    expect(
      verifyMediaSig({
        assetId,
        exp: Number(parsed.searchParams.get("exp")),
        sig: parsed.searchParams.get("sig") ?? "",
        secret,
        nowSec: nowSec + 10,
      }),
    ).toBe(true);
  });

  it("rejects expired and tampered signatures", () => {
    const url = signMediaUrl({
      assetId,
      baseUrl: "http://localhost:3001",
      secret,
      nowSec,
      ttlSec: 60,
    });
    const sig = new URL(url).searchParams.get("sig") ?? "";
    expect(
      verifyMediaSig({ assetId, exp: nowSec + 60, sig, secret, nowSec: nowSec + 120 }),
    ).toBe(false);
    expect(
      verifyMediaSig({ assetId, exp: nowSec + 60, sig: "ab".repeat(32), secret, nowSec }),
    ).toBe(false);
  });
});
