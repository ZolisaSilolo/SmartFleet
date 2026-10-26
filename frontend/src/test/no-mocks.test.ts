import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name: string) => {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) return name === 'test' ? [] : sources(full);
    return /\.(ts|tsx)$/.test(name) ? [full] : [];
  });
}

describe('production bundle contains no mock, demo or dev-identity code', () => {
  const files = sources(join(process.cwd(), 'src'));
  const forbidden: Array<[RegExp, string]> = [
    [/seedDemo|INITIAL_DEMO|getStored|setStored/i, 'demo data store'],
    [/X-Dev-(Tenant|User)-Id/i, 'development identity headers'],
    [/smartfleet_tenant_id|smartfleet_token/, 'client-chosen tenant / token in storage'],
    [/DETERMINISTIC_HARNESS|AGENTCORE_FALLBACK/i, 'heuristic agent fallback'],
    [/localStorage\.|localStorage\[/, 'localStorage usage (tokens live in sessionStorage)'],
    [/fonts\.googleapis\.com/, 'third-party font CDN'],
  ];

  it.each(forbidden)('has no %s', (pattern, label) => {
    const offenders = files.filter((file) => pattern.test(readFileSync(file, 'utf8')));
    expect(offenders, `${label} found in ${offenders.join(', ')}`).toEqual([]);
  });
});
