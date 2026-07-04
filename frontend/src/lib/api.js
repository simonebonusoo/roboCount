const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

function buildUrl(path) {
  const normalizedPath = path.startsWith("/api/") ? path.slice(4) : path;
  return `${API_BASE_URL}${normalizedPath.startsWith("/") ? normalizedPath : `/${normalizedPath}`}`;
}

async function request(path, options = {}) {
  const response = await fetch(buildUrl(path), {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : null;

  if (!response.ok) {
    const detail = Array.isArray(data?.detail)
      ? data.detail.join(" ")
      : data?.detail || "Operazione non riuscita.";
    const error = new Error(detail);
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

export { API_BASE_URL };
