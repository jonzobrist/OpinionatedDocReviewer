'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

import { apiFetch } from '../../src/lib/api';
import {
  DocumentCommitRead,
  DocumentLibraryEntry,
  ReviewJobRead,
} from '../../src/lib/types';

function normalizeError(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  return 'Unexpected error';
}

type HistoryPanelProps = {
  libraryEntries: DocumentLibraryEntry[];
  selectedDocumentId: number | null;
  onStatus: (message: string | null) => void;
  onError: (message: string | null) => void;
};

export function HistoryPanel({
  libraryEntries,
  selectedDocumentId,
  onStatus,
  onError,
}: HistoryPanelProps) {
  const router = useRouter();
  const [historyDocumentId, setHistoryDocumentId] = useState<number | null>(
    selectedDocumentId ?? libraryEntries[0]?.id ?? null,
  );
  const [historyJobs, setHistoryJobs] = useState<ReviewJobRead[]>([]);
  const [commits, setCommits] = useState<DocumentCommitRead[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasUserChosenDoc, setHasUserChosenDoc] = useState(false);

  // When libraryEntries populates after mount (async fetch), pick a
  // sensible default document so the panel shows real content instead
  // of the empty-state placeholder. User-driven selection takes priority.
  useEffect(() => {
    if (hasUserChosenDoc) return;
    if (historyDocumentId !== null) return;
    const next = selectedDocumentId ?? libraryEntries[0]?.id ?? null;
    if (next !== null) setHistoryDocumentId(next);
  }, [libraryEntries, selectedDocumentId, historyDocumentId, hasUserChosenDoc]);

  async function loadCommits(documentId: number): Promise<void> {
    try {
      const result = await apiFetch<DocumentCommitRead[]>(`/documents/${documentId}/history`);
      setCommits(result);
    } catch {
      setCommits([]);
    }
  }

  async function loadHistoryJobs(): Promise<void> {
    try {
      const jobs = await apiFetch<ReviewJobRead[]>('/review-jobs');
      setHistoryJobs(Array.isArray(jobs) ? jobs : []);
    } catch (error) {
      onError(normalizeError(error));
      setHistoryJobs([]);
    }
  }

  async function refresh(documentId: number | null): Promise<void> {
    setIsLoading(true);
    try {
      await loadHistoryJobs();
      if (documentId) {
        await loadCommits(documentId);
      } else {
        setCommits([]);
      }
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void refresh(historyDocumentId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [historyDocumentId]);

  return (
    <div className="library-overlay">
      <div className="library-shell">
        <div className="library-header">
          <div>
            <div className="library-title">History</div>
            <div className="library-sub">
              Review runs across your workspace and Git-backed document commits.
            </div>
          </div>
          <div className="library-actions">
            <select
              className="input compact"
              value={historyDocumentId ?? ''}
              onChange={(event) => {
                setHasUserChosenDoc(true);
                const raw = event.target.value;
                if (!raw) {
                  setHistoryDocumentId(null);
                  return;
                }
                const next = Number(raw);
                setHistoryDocumentId(Number.isFinite(next) ? next : null);
              }}
            >
              <option value="">No document selected</option>
              {libraryEntries.map((entry) => (
                <option key={`history-doc-${entry.id}`} value={entry.id}>
                  {entry.title}
                </option>
              ))}
            </select>
            <button
              className="ghost-button"
              type="button"
              onClick={() => void refresh(historyDocumentId)}
              disabled={isLoading}
            >
              {isLoading ? 'Refreshing…' : 'Refresh'}
            </button>
            {historyDocumentId && (
              <button
                className="primary-button"
                type="button"
                onClick={() => router.push(`/?doc=${historyDocumentId}`)}
              >
                Open Document
              </button>
            )}
          </div>
        </div>

        <div className="admin-grid">
          <section className="admin-card wide">
            <div className="drawer-title">Review Runs</div>
            <div className="history-list">
              {historyJobs.length === 0 && (
                <div className="subtle">No review runs yet.</div>
              )}
              {historyJobs.map((job) => (
                <div key={`history-job-${job.id}`} className="history-item">
                  <div>
                    <div className="history-msg">
                      #{job.id} {job.status} · version {job.document_version_id}
                    </div>
                    <div className="history-time">
                      {new Date(job.created_at).toLocaleString()}
                      {job.completed_at
                        ? ` · completed ${new Date(job.completed_at).toLocaleString()}`
                        : ''}
                    </div>
                  </div>
                  <span className="pill">
                    {job.provider}/{job.model}
                  </span>
                </div>
              ))}
            </div>
          </section>

          <section className="admin-card wide">
            <div className="drawer-title">Document Commits</div>
            <div className="history-list">
              {!historyDocumentId && (
                <div className="subtle">Select a document to view commit history.</div>
              )}
              {historyDocumentId && commits.length === 0 && (
                <div className="subtle">No commits yet for this document.</div>
              )}
              {commits.map((commit) => (
                <div key={`history-commit-${commit.sha}`} className="history-item">
                  <div>
                    <div className="history-msg">{commit.message}</div>
                    <div className="history-time">
                      {new Date(commit.authored_at).toLocaleString()}
                    </div>
                  </div>
                  <span className="pill">{commit.sha.slice(0, 7)}</span>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

export default HistoryPanel;
