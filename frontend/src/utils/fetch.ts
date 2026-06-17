export async function fetchFromBest(urls: string[], timeoutMs = 2000): Promise<any> {
  for (const url of urls) {
    try {
      const r = await fetch(url, { signal: AbortSignal.timeout(timeoutMs) });
      if (r.ok) return r.json();
    } catch {}
  }
  return null;
}
