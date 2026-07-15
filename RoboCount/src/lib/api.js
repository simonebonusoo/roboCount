import { invalidateAppData } from "./queryClient";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";
const APP_DATA_CHANGED_EVENT = "monitor-spese:data-changed";
const APP_AUTH_EXPIRED_EVENT = "monitor-spese:auth-expired";
const GET_RETRY_DELAY_MS = 250;

function buildUrl(path) {
  const normalizedPath = path.startsWith("/api/") ? path.slice(4) : path;
  return `${API_BASE_URL}${normalizedPath.startsWith("/") ? normalizedPath : `/${normalizedPath}`}`;
}

function wait(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function notifyAuthExpired() {
  if (typeof window === "undefined") {
    return;
  }
  window.dispatchEvent(new Event(APP_AUTH_EXPIRED_EVENT));
}

async function parseResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : null;
  return { data };
}

function buildErrorMessage(response, data) {
  if (Array.isArray(data?.detail)) {
    return data.detail.join(" ");
  }
  if (typeof data?.detail === "string" && data.detail.trim()) {
    if (data.detail.toLowerCase().includes("internal server error")) {
      return "Non e stato possibile completare l'operazione. Riprova.";
    }
    return data.detail;
  }
  if (response.status === 401) {
    return "Sessione scaduta. Effettua di nuovo l'accesso.";
  }
  if (response.status >= 500) {
    return "Non e stato possibile completare l'operazione. Riprova.";
  }
  if (response.statusText && !response.statusText.toLowerCase().includes("internal server error")) {
    return response.statusText;
  }
  return "Operazione non riuscita.";
}

function buildNetworkErrorMessage(error) {
  const message = String(error?.message || "").toLowerCase();
  if (message.includes("failed to fetch") || message.includes("networkerror")) {
    return "Impossibile contattare il backend. Verifica che RoboCount sia avviato correttamente e riprova.";
  }
  return "Connessione al server non riuscita. Riprova.";
}

async function request(path, options = {}, attempt = 0) {
  const method = String(options.method || "GET").toUpperCase();
  const isRetryableGet = method === "GET";

  let response;
  try {
    response = await fetch(buildUrl(path), {
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
      ...options,
    });
  } catch (error) {
    if (isRetryableGet && attempt === 0) {
      await wait(GET_RETRY_DELAY_MS);
      return request(path, options, attempt + 1);
    }
    const networkError = new Error(buildNetworkErrorMessage(error));
    networkError.cause = error;
    throw networkError;
  }

  const { data } = await parseResponse(response);

  if (!response.ok) {
    if (response.status === 401) {
      notifyAuthExpired();
    }

    if (isRetryableGet && attempt === 0 && response.status >= 500) {
      await wait(GET_RETRY_DELAY_MS);
      return request(path, options, attempt + 1);
    }

    const error = new Error(buildErrorMessage(response, data));
    error.status = response.status;
    error.payload = data;
    throw error;
  }

  return data;
}

export const api = {
  get: (path) => request(path),
  post: (path, body) =>
    request(path, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  put: (path, body) =>
    request(path, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  patch: (path, body) =>
    request(path, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  delete: (path) =>
    request(path, {
      method: "DELETE",
    }),
};

export function notifyAppDataChanged(detail = { scope: "all" }) {
  void invalidateAppData(detail?.scope || "all");
  window.dispatchEvent(new CustomEvent(APP_DATA_CHANGED_EVENT, { detail }));
}

export function subscribeAppDataChanged(callback) {
  function handler(event) {
    callback(event.detail || { scope: "all" });
  }

  window.addEventListener(APP_DATA_CHANGED_EVENT, handler);
  return () => window.removeEventListener(APP_DATA_CHANGED_EVENT, handler);
}

export function subscribeAuthExpired(callback) {
  function handler() {
    callback();
  }

  window.addEventListener(APP_AUTH_EXPIRED_EVENT, handler);
  return () => window.removeEventListener(APP_AUTH_EXPIRED_EVENT, handler);
}

export { API_BASE_URL };
