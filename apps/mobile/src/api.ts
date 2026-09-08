export const apiBaseUrl = () =>
  process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:3002";

export async function api(
  path: string,
  opts: RequestInit & { token?: string } = {},
) {
  const headers = new Headers(opts.headers);
  if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (opts.token) headers.set("Authorization", `Bearer ${opts.token}`);
  const { token: _token, ...rest } = opts;
  return fetch(`${apiBaseUrl()}${path}`, { ...rest, headers });
}
