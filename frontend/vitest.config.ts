import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'node',
    include: ['tests/**/*.test.ts', 'tests/**/*.test.tsx'],
    // Page-level integration tests exercise a 5,000-line component with
    // polling, URL sync, and async meta loading effects that interact.
    // There is a known race (tracked for the P1 frontend split) where
    // setSelectedReviewJobId from the 1.2s poll can reset
    // commentModeSelectionSource back to 'auto' during a manual Meta-mode
    // click, occasionally triggering the missing-meta fallback. Empirical
    // flake rate locally is ~1/30; CI (slower) is ~1/4. Retry guards CI
    // from this until the root-cause refactor lands.
    retry: 2
  }
});
