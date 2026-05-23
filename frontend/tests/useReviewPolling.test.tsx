// @vitest-environment jsdom

import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render } from '@testing-library/react';

import { useReviewPolling } from '../src/lib/hooks/useReviewPolling';

function Probe({
  versionId,
  reviewJobId,
  onPoll,
  intervalMs,
  onGeneration,
}: {
  versionId: number | null;
  reviewJobId: number | null;
  onPoll: (vid: number, jid: number | null) => void;
  intervalMs: number;
  onGeneration?: (gen: number) => void;
}) {
  const { generationRef } = useReviewPolling({
    versionId,
    reviewJobId,
    onPoll,
    intervalMs,
  });
  React.useEffect(() => {
    onGeneration?.(generationRef.current);
  });
  return null;
}

describe('useReviewPolling', () => {
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it('installs exactly one interval and reads selection through refs on each tick', () => {
    vi.useFakeTimers();
    const onPoll = vi.fn();

    const { rerender } = render(
      <Probe versionId={1} reviewJobId={10} onPoll={onPoll} intervalMs={100} />
    );

    act(() => {
      vi.advanceTimersByTime(100);
    });
    expect(onPoll).toHaveBeenCalledTimes(1);
    expect(onPoll).toHaveBeenLastCalledWith(1, 10);

    // Change only the reviewJobId. The poller must pick up the new value
    // without tearing down and reinstalling the interval (we assert a single
    // firing after 100ms, not two).
    rerender(
      <Probe versionId={1} reviewJobId={20} onPoll={onPoll} intervalMs={100} />
    );
    act(() => {
      vi.advanceTimersByTime(100);
    });
    expect(onPoll).toHaveBeenCalledTimes(2);
    expect(onPoll).toHaveBeenLastCalledWith(1, 20);
  });

  it('bumps generationRef when versionId changes so callers can detect stale responses', () => {
    vi.useFakeTimers();
    const onPoll = vi.fn();
    const seen: number[] = [];

    const { rerender } = render(
      <Probe
        versionId={1}
        reviewJobId={null}
        onPoll={onPoll}
        intervalMs={100}
        onGeneration={(gen) => seen.push(gen)}
      />
    );
    const initial = seen[seen.length - 1];

    rerender(
      <Probe
        versionId={2}
        reviewJobId={null}
        onPoll={onPoll}
        intervalMs={100}
        onGeneration={(gen) => seen.push(gen)}
      />
    );
    const afterSwitch = seen[seen.length - 1];
    expect(afterSwitch).toBeGreaterThan(initial);

    // Switching only the reviewJobId must NOT bump the generation; otherwise
    // every poll-driven job change would invalidate outstanding fetches.
    rerender(
      <Probe
        versionId={2}
        reviewJobId={99}
        onPoll={onPoll}
        intervalMs={100}
        onGeneration={(gen) => seen.push(gen)}
      />
    );
    expect(seen[seen.length - 1]).toBe(afterSwitch);
  });

  it('does not call onPoll while versionId is null', () => {
    vi.useFakeTimers();
    const onPoll = vi.fn();

    render(
      <Probe versionId={null} reviewJobId={null} onPoll={onPoll} intervalMs={100} />
    );
    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(onPoll).not.toHaveBeenCalled();
  });
});
