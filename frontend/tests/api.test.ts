import { describe, expect, it } from 'vitest';
import { buildHeaders, DEFAULT_TENANT } from '../src/lib/api';
import { deriveTitle } from '../src/lib/deriveTitle';

describe('api helpers', () => {
  it('builds headers with default tenant', () => {
    const headers = buildHeaders();
    expect(headers['Content-Type']).toBe('application/json');
    expect(headers['X-Tenant-Id']).toBe(DEFAULT_TENANT);
  });
});

describe('deriveTitle', () => {
  it('uses filename first', () => {
    expect(deriveTitle('notes.md', '# Hello World\nBody')).toBe('notes');
  });

  it('normalizes separators in filename', () => {
    expect(deriveTitle('release_notes.md', 'No heading')).toBe('release notes');
  });
});
