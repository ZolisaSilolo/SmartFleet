import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/auth', () => ({ getIdToken: vi.fn() }));

import { getIdToken } from '../services/auth';
import { ApiRequestError, listAll, request, SESSION_EXPIRED_EVENT } from '../services/http';

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status });

describe('http client', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
    vi.mocked(getIdToken).mockResolvedValue('id-token');
  });
  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  it('sends the Cognito ID token and never a tenant header', async () => {
    fetchMock.mockResolvedValue(json(200, { ok: true }));
    await request('GET', '/vehicles');
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/vehicles');
    expect(init.headers.Authorization).toBe('Bearer id-token');
    expect(JSON.stringify(init.headers).toLowerCase()).not.toContain('tenant');
  });

  it('refuses to call the API when signed out and tells the app the session ended', async () => {
    vi.mocked(getIdToken).mockResolvedValue(null);
    const expired = vi.fn();
    window.addEventListener(SESSION_EXPIRED_EVENT, expired);
    await expect(request('GET', '/vehicles')).rejects.toMatchObject({ status: 401, code: 'UNAUTHORIZED' });
    expect(fetchMock).not.toHaveBeenCalled();
    expect(expired).toHaveBeenCalled();
    window.removeEventListener(SESSION_EXPIRED_EVENT, expired);
  });

  it('surfaces API errors with their stable code instead of faking data', async () => {
    fetchMock.mockResolvedValue(json(503, { error: { code: 'AI_UNAVAILABLE', message: 'The AI service is temporarily unavailable.' } }));
    const error = await request('POST', '/agent/chat', { message: 'hi' }).catch((e) => e);
    expect(error).toBeInstanceOf(ApiRequestError);
    expect(error).toMatchObject({ status: 503, code: 'AI_UNAVAILABLE' });
  });

  it('reports network failures as errors (no offline fallback)', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));
    await expect(request('GET', '/trips')).rejects.toMatchObject({ code: 'NETWORK_ERROR' });
  });

  it('listAll follows nextToken until the last page', async () => {
    fetchMock
      .mockResolvedValueOnce(json(200, { items: [{ id: 1 }, { id: 2 }], nextToken: 'abc' }))
      .mockResolvedValueOnce(json(200, { items: [{ id: 3 }], nextToken: null }));
    const items = await listAll<{ id: number }>('/trips', { status: 'COMPLETED' });
    expect(items.map((i) => i.id)).toEqual([1, 2, 3]);
    expect(fetchMock.mock.calls[0][0]).toContain('limit=200');
    expect(fetchMock.mock.calls[0][0]).toContain('status=COMPLETED');
    expect(fetchMock.mock.calls[1][0]).toContain('nextToken=abc');
  });

  it('listAll fails loudly instead of silently truncating huge result sets', async () => {
    fetchMock.mockImplementation(async () => json(200, { items: [], nextToken: 'more' }));
    await expect(listAll('/trips')).rejects.toMatchObject({ code: 'TOO_MANY_RECORDS' });
  });
});
