import { getIdToken } from './auth';
import { config } from './config';
import { Page } from '../types';

export class ApiRequestError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = 'ApiRequestError';
  }
}

export const SESSION_EXPIRED_EVENT = 'smartfleet:session-expired';
const REQUEST_TIMEOUT_MS = 30000;
const PAGE_SIZE = 200;
const MAX_PAGES = 25;

type Query = Record<string, string | number | undefined>;

function buildUrl(path: string, query?: Query): string {
  const params = new URLSearchParams();
  Object.entries(query ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== '') params.set(key, String(value));
  });
  const qs = params.toString();
  return `${config.apiBase}${path}${qs ? `?${qs}` : ''}`;
}

export async function request<T>(method: string, path: string, body?: unknown, query?: Query): Promise<T> {
  const token = await getIdToken();
  if (!token) {
    window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    throw new ApiRequestError(401, 'UNAUTHORIZED', 'Your session has expired. Please sign in again.');
  }

  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(buildUrl(path, query), {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });

    const text = await response.text();
    const payload = text ? JSON.parse(text) : null;

    if (response.status === 401) {
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    }
    if (!response.ok) {
      const err = payload?.error;
      throw new ApiRequestError(response.status, err?.code ?? 'REQUEST_FAILED', err?.message ?? `Request failed (${response.status})`);
    }
    return payload as T;
  } catch (error) {
    if (error instanceof ApiRequestError) throw error;
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiRequestError(0, 'TIMEOUT', 'The request timed out. Please try again.');
    }
    throw new ApiRequestError(0, 'NETWORK_ERROR', 'Unable to reach the server. Check your connection and try again.');
  } finally {
    window.clearTimeout(timer);
  }
}

/** Follow nextToken until exhausted. Throws (never silently truncates) if the dataset exceeds the display cap. */
export async function listAll<T>(path: string, query: Query = {}): Promise<T[]> {
  const items: T[] = [];
  let token: string | null = null;
  for (let page = 0; page < MAX_PAGES; page += 1) {
    const result: Page<T> = await request<Page<T>>('GET', path, undefined, {
      ...query,
      limit: PAGE_SIZE,
      nextToken: token ?? undefined,
    });
    items.push(...result.items);
    token = result.nextToken;
    if (!token) return items;
  }
  throw new ApiRequestError(0, 'TOO_MANY_RECORDS', `More than ${MAX_PAGES * PAGE_SIZE} records match. Apply a filter to narrow the list.`);
}
