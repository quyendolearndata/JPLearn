const base = () => process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3001";

export async function api(
  path: string,
  opts: RequestInit & { token?: string } = {},
) {
  const headers = new Headers(opts.headers);
  const isForm = typeof FormData !== "undefined" && opts.body instanceof FormData;
  if (!isForm && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (opts.token) headers.set("Authorization", `Bearer ${opts.token}`);
  const { token: _token, ...rest } = opts;
  return fetch(`${base()}${path}`, { ...rest, headers });
}
