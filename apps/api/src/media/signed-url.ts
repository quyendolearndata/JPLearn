import { createHmac, timingSafeEqual } from "node:crypto";

const DEFAULT_TTL_SEC = 60 * 60;

function signingSecret(explicit?: string): string {
  const secret = explicit ?? process.env.MEDIA_SIGNING_SECRET ?? process.env.JWT_SECRET;
  if (!secret) throw new Error("MEDIA_SIGNING_SECRET or JWT_SECRET must be set");
  return secret;
}

function hmacHex(secret: string, assetId: string, exp: number): string {
  return createHmac("sha256", secret).update(`${assetId}:${exp}`).digest("hex");
}

export function signMediaUrl(input: {
  assetId: string;
  baseUrl: string;
  secret?: string;
  nowSec?: number;
  ttlSec?: number;
}): string {
  const nowSec = input.nowSec ?? Math.floor(Date.now() / 1000);
  const ttlSec = input.ttlSec ?? DEFAULT_TTL_SEC;
  const exp = nowSec + ttlSec;
  const sig = hmacHex(signingSecret(input.secret), input.assetId, exp);
  const base = input.baseUrl.replace(/\/$/, "");
  return `${base}/media/${input.assetId}?exp=${exp}&sig=${sig}`;
}

export function publicApiBaseUrl(): string {
  const baseUrl = process.env.API_PUBLIC_URL;
  if (!baseUrl) throw new Error("API_PUBLIC_URL must be set");
  return baseUrl.replace(/\/$/, "");
}

export function signedPlaybackForAsset(assetId: string): string {
  return signMediaUrl({ assetId, baseUrl: publicApiBaseUrl() });
}

export function signedHlsForAsset(assetId: string, file = "index.m3u8"): string {
  return signHlsUrl({ assetId, baseUrl: publicApiBaseUrl(), file });
}

export function signHlsUrl(input: {
  assetId: string;
  baseUrl: string;
  file?: string;
  secret?: string;
  nowSec?: number;
  ttlSec?: number;
}): string {
  const unsigned = signMediaUrl({ ...input, ttlSec: input.ttlSec, nowSec: input.nowSec, secret: input.secret });
  const u = new URL(unsigned);
  const file = input.file ?? "index.m3u8";
  u.pathname = `/media/${input.assetId}/hls/${file}`;
  return u.toString();
}

export function verifyMediaSig(input: {
  assetId: string;
  exp: number;
  sig: string;
  secret?: string;
  nowSec?: number;
}): boolean {
  if (!Number.isFinite(input.exp) || input.sig.length !== 64) return false;
  const nowSec = input.nowSec ?? Math.floor(Date.now() / 1000);
  if (input.exp < nowSec) return false;
  const expected = hmacHex(signingSecret(input.secret), input.assetId, input.exp);
  try {
    return timingSafeEqual(Buffer.from(expected, "hex"), Buffer.from(input.sig, "hex"));
  } catch {
    return false;
  }
}
