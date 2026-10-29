let accessToken: string | null = null;

export const setToken = (t: string | null) => {
  accessToken = t;
};

export const getToken = (): string | null => {
  return accessToken;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

let isRefreshing = false;
let refreshPromise: Promise<boolean> | null = null;

export async function refresh(): Promise<boolean> {
  if (isRefreshing && refreshPromise) {
    return refreshPromise;
  }
  isRefreshing = true;
  refreshPromise = (async () => {
    try {
      const res = await fetch("/api/v1/auth/refresh", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) {
        setToken(null);
        return false;
      }
      const data = await res.json();
      const token = data?.data?.accessToken ?? data?.accessToken ?? data?.token;
      if (token) {
        setToken(token);
        return true;
      }
      setToken(null);
      return false;
    } catch {
      setToken(null);
      return false;
    } finally {
      isRefreshing = false;
      refreshPromise = null;
    }
  })();
  return refreshPromise;
}

export async function raw(
  path: string,
  init: RequestInit = {},
  retry = true,
): Promise<any> {
  const normalizedPath = path.startsWith("/api/v1") ? path : `/api/v1${path}`;
  const res = await fetch(normalizedPath, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...init.headers,
    },
  });

  if (
    res.status === 401 &&
    retry &&
    !normalizedPath.includes("/auth/refresh") &&
    !normalizedPath.includes("/auth/login")
  ) {
    const refreshed = await refresh();
    if (refreshed) {
      return raw(path, init, false);
    }
  }

  const body = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) {
    throw new ApiError(
      res.status,
      body?.error?.code ?? "UNKNOWN",
      body?.error?.message ?? "Request failed",
      body?.error?.details,
    );
  }
  return body;
}

export const http = {
  get: <T = any>(p: string): Promise<T> => raw(p),
  post: <T = any>(p: string, b?: unknown): Promise<T> =>
    raw(p, { method: "POST", body: JSON.stringify(b ?? {}) }),
  patch: <T = any>(p: string, b?: unknown): Promise<T> =>
    raw(p, { method: "PATCH", body: JSON.stringify(b ?? {}) }),
  del: <T = any>(p: string): Promise<T> => raw(p, { method: "DELETE" }),
};
