// Simple in-memory cache for price history API responses.
// Prevents duplicate backend calls when PriceChart remounts with the same params
// (e.g. during streaming → final message transition).

interface CacheEntry {
  data: any;
  timestamp: number;
}

const cache = new Map<string, CacheEntry>();
const inflight = new Map<string, Promise<any>>();

const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

function buildKey(fundCodes: string[], startDate: string, endDate: string): string {
  return `${fundCodes.sort().join(',')}|${startDate}|${endDate}`;
}

export async function fetchPriceHistory(
  fundCodes: string[],
  startDate: string,
  endDate: string,
): Promise<any> {
  const key = buildKey(fundCodes, startDate, endDate);

  // 1. Return from cache if fresh
  const cached = cache.get(key);
  if (cached && Date.now() - cached.timestamp < CACHE_TTL_MS) {
    return cached.data;
  }

  // 2. Deduplicate in-flight requests
  const existing = inflight.get(key);
  if (existing) {
    return existing;
  }

  // 3. Make the actual request
  const promise = (async () => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';
    const body =
      fundCodes.length === 1
        ? { fund_code: fundCodes[0], start_date: startDate, end_date: endDate }
        : { fund_codes: fundCodes, start_date: startDate, end_date: endDate };

    const resp = await fetch(`${apiUrl}/api/pricehistory`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!resp.ok) {
      const detail = await resp.json().catch(() => null);
      throw new Error(detail?.detail || `HTTP ${resp.status}`);
    }

    const data = await resp.json();
    cache.set(key, { data, timestamp: Date.now() });
    return data;
  })();

  inflight.set(key, promise);

  try {
    return await promise;
  } finally {
    inflight.delete(key);
  }
}
