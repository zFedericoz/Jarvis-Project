export async function fetchFromBest(urls: string[], timeoutMs = 2000): Promise<any> {
  for (const url of urls) {
    try {
      const r = await fetch(url, { signal: AbortSignal.timeout(timeoutMs) });
      if (r.ok) return r.json();
    } catch {}
  }
  return null;
}

export async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  const token = localStorage.getItem("jwt_token");
  const headers = new Headers(options.headers || {});
  // Non sovrascrivere Content-Type per FormData (il browser lo imposta automaticamente)
  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(url, { ...options, headers });
  if (response.status === 401) {
    localStorage.removeItem("jwt_token");
    localStorage.removeItem("jwt_user");
    window.dispatchEvent(new CustomEvent("auth:expired"));
  }
  return response;
}
