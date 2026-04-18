import { useEffect, useRef, type MutableRefObject } from 'react';

export const DEFAULT_POLL_INTERVAL_MS = 1200;

export type PollCallback = (
  versionId: number,
  reviewJobId: number | null,
) => void | Promise<void>;

/**
 * Encapsulates the review-polling lifecycle that is otherwise prone to
 * stale-closure bugs when bound to changing state via effect dependencies.
 *
 * - The interval is installed exactly once (empty dep array). It reads the
 *   current selection through refs on each tick, so rapid doc-switches do
 *   not leave ghost intervals polling the previously-selected version.
 * - A monotonic `generationRef` is bumped whenever `versionId` changes.
 *   Callers that issue async fetches can capture the value at call-site
 *   and drop state-writes whose generation no longer matches the current
 *   one — preventing out-of-order responses from overwriting fresh state.
 *
 * All ref-syncing lives in a single effect to avoid adding extra render
 * cycles beyond what the inline pattern required. Each additional effect
 * adds a commit-phase tick and an extra microtask flush under Testing
 * Library, which surfaces as findByText timeouts in CI where the default
 * 1000ms window is tight.
 */
export function useReviewPolling(opts: {
  versionId: number | null;
  reviewJobId: number | null;
  onPoll: PollCallback;
  intervalMs?: number;
}): { generationRef: MutableRefObject<number> } {
  const versionIdRef = useRef(opts.versionId);
  const reviewJobIdRef = useRef(opts.reviewJobId);
  const onPollRef = useRef(opts.onPoll);
  const generationRef = useRef(0);
  const lastVersionIdRef = useRef(opts.versionId);
  const intervalMs = opts.intervalMs ?? DEFAULT_POLL_INTERVAL_MS;

  useEffect(() => {
    versionIdRef.current = opts.versionId;
    reviewJobIdRef.current = opts.reviewJobId;
    onPollRef.current = opts.onPoll;
    if (lastVersionIdRef.current !== opts.versionId) {
      generationRef.current += 1;
      lastVersionIdRef.current = opts.versionId;
    }
  });

  useEffect(() => {
    const interval = setInterval(() => {
      const vid = versionIdRef.current;
      if (!vid) return;
      void onPollRef.current(vid, reviewJobIdRef.current);
    }, intervalMs);
    return () => clearInterval(interval);
  }, [intervalMs]);

  return { generationRef };
}
