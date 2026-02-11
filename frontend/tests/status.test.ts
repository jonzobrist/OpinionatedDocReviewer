import { describe, expect, it } from 'vitest';
import type { SystemStatus } from '../src/lib/types';

describe('SystemStatus type', () => {
  it('has expected shape', () => {
    const status: SystemStatus = {
      redis: { ok: true, error: null },
      llm: { provider: 'openai', ok: false, error: 'missing key' },
      openai: { ok: false },
      review_queue: 'review-jobs',
      doc_repo_enabled: true
    };
    expect(status.redis.ok).toBe(true);
    expect(status.openai.ok).toBe(false);
  });
});
