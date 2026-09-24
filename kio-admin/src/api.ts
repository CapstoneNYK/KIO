export const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const TOKEN_KEY = "kio_admin_token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (token: string) => localStorage.setItem(TOKEN_KEY, token);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

export const getUsername = (): string | null => {
  const token = getToken();
  if (!token) return null;
  try {
    const payload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const json = decodeURIComponent(
      atob(payload).split("").map((c) => "%" + c.charCodeAt(0).toString(16).padStart(2, "0")).join("")
    );
    return (JSON.parse(json) as { sub?: string }).sub ?? null;
  } catch {
    return null;
  }
};

export const authHeaders = (): HeadersInit => {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
};

export const UNAUTHORIZED_EVENT = "kio-admin-unauthorized";

const errorDetail = async (res: Response, fallback: string) => {
  const body = await res.json().catch(() => null);
  const detail = body?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg as string;
  return fallback;
};

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: { ...authHeaders(), ...(init?.headers ?? {}) },
  });
  if (res.status === 401) {
    clearToken();
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    throw new Error(`API 401: ${path}`);
  }
  if (!res.ok) throw new Error(await errorDetail(res, `요청에 실패했습니다. (${res.status})`));
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
