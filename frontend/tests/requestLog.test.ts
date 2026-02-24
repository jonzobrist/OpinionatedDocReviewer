import { describe, expect, it } from 'vitest';

import { summarizeForwardedHeaders } from '../src/lib/requestLog';

describe('summarizeForwardedHeaders', () => {
  it('returns forwarded values when present', () => {
    const headers = new Headers({
      'x-forwarded-for': '203.0.113.10, 10.0.0.1',
      'x-real-ip': '203.0.113.10'
    });
    const summary = summarizeForwardedHeaders(headers);
    expect(summary.xForwardedFor).toBe('203.0.113.10, 10.0.0.1');
    expect(summary.xRealIp).toBe('203.0.113.10');
  });

  it('returns dashes when headers are missing', () => {
    const summary = summarizeForwardedHeaders(new Headers());
    expect(summary.xForwardedFor).toBe('-');
    expect(summary.xRealIp).toBe('-');
  });
});
