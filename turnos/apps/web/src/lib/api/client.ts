import createClient from "openapi-fetch";
import type { paths } from "./schema";

/** Erro da API no formato RFC 9457, com o `code` estável que a UI usa. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly violations: { code: string; severity: string; date: string; message: string }[] = [],
  ) {
    super(message);
  }
}

let refreshing: Promise<boolean> | null = null;

/** Uma só renovação de sessão de cada vez, mesmo com vários pedidos a falhar em simultâneo. */
function refreshSession(): Promise<boolean> {
  refreshing ??= fetch("/api/v1/auth/refresh", { method: "POST", headers: { "X-Requested-With": "turnos" } })
    .then((r) => r.ok)
    .catch(() => false)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

async function apiFetch(request: Request): Promise<Response> {
  request.headers.set("X-Requested-With", "turnos");
  const retry = request.clone();
  const res = await fetch(request);
  if (res.status === 401 && !new URL(request.url).pathname.startsWith("/api/v1/auth/")) {
    if (await refreshSession()) {
      return fetch(retry);
    }
  }
  return res;
}

export const api = createClient<paths>({ baseUrl: typeof window === "undefined" ? "http://localhost" : window.location.origin, fetch: apiFetch });

type Result<T> = { data?: T; error?: unknown; response: Response };

/** Desembrulha a resposta do openapi-fetch: devolve os dados ou lança {@link ApiError}. */
export async function unwrap<T>(p: Promise<Result<T>>): Promise<T> {
  const { data, error, response } = await p;
  if (!response.ok) {
    const body = (error ?? {}) as { code?: string; detail?: string; violations?: ApiError["violations"] };
    throw new ApiError(response.status, body.code ?? `http-${response.status}`, body.detail ?? "Não foi possível concluir o pedido", body.violations ?? []);
  }
  return data as T;
}
