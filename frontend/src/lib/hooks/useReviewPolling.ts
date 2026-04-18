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
  const intervalMs = opts.intervalMs ?? DEFAULT_POLL_INTERVAL_MS;

  useEffect(() => {
    versionIdRef.current = opts.versionId;
    generationRef.current += 1;
  }, [opts.versionId]);

  useEffect(() => {
    reviewJobIdRef.current = opts.reviewJobId;
  }, [opts.reviewJobId]);

  useEffect(() => {
    onPollRef.current = opts.onPoll;
  }, [opts.onPoll]);

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
