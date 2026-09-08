import fs from "node:fs";
import path from "node:path";

const STOCK_RELATIVE = "media/stock/mp4/level-0-wash-hands.mp4";

export function stockMp4Path(): string {
  const candidates = [
    process.env.JPLEARN_E2E_SOURCE_MP4,
    path.resolve(__dirname, `../../../${STOCK_RELATIVE}`),
    path.resolve(process.cwd(), `../../${STOCK_RELATIVE}`),
  ].filter((candidate): candidate is string => Boolean(candidate));
  const hit = candidates.find((candidate) => fs.existsSync(candidate));
  if (!hit) throw new Error("stock mp4 missing");
  return hit;
}

export function stockMp4Buffer(): Buffer {
  return fs.readFileSync(stockMp4Path());
}
