export const getApiBaseUrl = () => {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3002";
};

export class ApiNetworkError extends Error {
  constructor(message: string, public cause?: unknown) {
    super(message);
    this.name = "ApiNetworkError";
  }
}

export interface ApiErrorResponse {
  statusCode: number;
  message: string;
  error?: string;
  details?: unknown;
}

export async function api(
  path: string,
  opts: RequestInit & { token?: string } = {},
): Promise<Response> {
  const headers = new Headers(opts.headers);
  const isForm = typeof FormData !== "undefined" && opts.body instanceof FormData;
  if (!isForm && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  let authToken = opts.token;
  if (!authToken && !headers.has("Authorization") && typeof window !== "undefined") {
    try {
      authToken = localStorage.getItem("jplearn.access_token") ?? undefined;
    } catch {
      // ignore
    }
  }
  if (authToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${authToken}`);
  }

  const { token: _token, ...rest } = opts;
  const url = `${getApiBaseUrl()}${path}`;

  let res: Response;
  try {
    res = await fetch(url, { ...rest, headers });
  } catch (err) {
    throw new ApiNetworkError(
      "Không thể kết nối đến máy chủ. Vui lòng kiểm tra kết nối mạng.",
      err,
    );
  }

  // Centralized 401 Unauthorized handling for authenticated requests
  const hadAuth = Boolean(authToken || headers.has("Authorization"));
  if (res.status === 401 && hadAuth && !path.startsWith("/auth/login") && !path.startsWith("/auth/register")) {
    if (typeof window !== "undefined") {
      try {
        const { clearSession } = await import("./auth-storage");
        clearSession();
        if (window.location.pathname !== "/login") {
          const currentPath = window.location.pathname + window.location.search;
          window.location.href = `/login?redirect=${encodeURIComponent(currentPath)}`;
        }
      } catch {
        // ignore storage import error
      }
    }
  }

  return res;
}

export async function parseApiResponse<T>(res: Response): Promise<T> {
  if (res.status === 204) {
    return null as T;
  }

  const text = await res.text();
  if (!text) {
    return null as T;
  }

  try {
    return JSON.parse(text) as T;
  } catch {
    return text as unknown as T;
  }
}

export async function parseApiError(res: Response): Promise<ApiErrorResponse> {
  let message = `Lỗi yêu cầu: mã ${res.status}`;
  let details: unknown = null;

  try {
    const data = await res.json();
    if (data && typeof data === "object") {
      details = data;
      if (typeof data.detail === "string") {
        message = data.detail;
      } else if (Array.isArray(data.detail)) {
        message = data.detail.map((d: { msg?: string }) => d.msg ?? JSON.stringify(d)).join(", ");
      } else if (typeof data.message === "string") {
        message = data.message;
      }
    }
  } catch {
    // If not json, use default message
  }

  return {
    statusCode: res.status,
    message,
    details,
  };
}

