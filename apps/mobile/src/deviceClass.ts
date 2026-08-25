export function deviceClassFrom(p: {
  os: string;
  width: number;
  height: number;
}): "phone" | "ipad" {
  const min = Math.min(p.width, p.height);
  if (p.os === "ios" && min >= 768) return "ipad";
  return "phone";
}
