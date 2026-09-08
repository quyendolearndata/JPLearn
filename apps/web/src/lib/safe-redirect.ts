/** R-07 / T-AUTH-SEC-001: only same-origin absolute paths are allowed as post-login targets. */
export function getSafeRedirect(target: string | null | undefined): string {
  if (!target) return "/";
  if (!target.startsWith("/")) return "/";
  if (target.startsWith("//") || target.startsWith("/\\")) return "/";
  if (target.includes("://") || target.includes("\\")) return "/";
  let decoded: string;
  try {
    decoded = decodeURIComponent(target);
  } catch {
    return "/";
  }
  if (decoded.startsWith("//") || decoded.startsWith("/\\") || decoded.includes("://")) return "/";
  return target;
}
