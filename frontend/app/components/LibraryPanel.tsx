'use client';

import React, { useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';

import { DocumentLibraryEntry } from '../../src/lib/types';

type LibraryFilter = 'all' | 'needs' | 'reviewed' | 'archived';

export type BulkProgress = {
  label: string;
  done: number;
  total: number;
} | null;

type LibraryPanelProps = {
  libraryEntries: DocumentLibraryEntry[];
  bulkProgress: BulkProgress;
  isBundleImporting: boolean;
  onImportBundle: (files: FileList) => Promise<void> | void;
  onBulkArchive: (archived: boolean, docIds: number[]) => Promise<void> | void;
  onBulkRerun: (targets: DocumentLibraryEntry[]) => Promise<void> | void;
  onBulkDelete: (docIds: number[]) => Promise<void> | void;
  onDeleteDocument: (docId: number, title: string) => Promise<void> | void;
  onSetArchived: (docId: number, archived: boolean) => Promise<void> | void;
};

export function LibraryPanel({
  libraryEntries,
  bulkProgress,
  isBundleImporting,
  onImportBundle,
  onBulkArchive,
  onBulkRerun,
  onBulkDelete,
  onDeleteDocument,
  onSetArchived,
}: LibraryPanelProps) {
  const router = useRouter();
  const [libraryFilter, setLibraryFilter] = useState<LibraryFilter>('all');
  const [librarySearch, setLibrarySearch] = useState('');
  const [selectedLibraryIds, setSelectedLibraryIds] = useState<Set<number>>(new Set());
  const [isLibraryHovering, setIsLibraryHovering] = useState(false);
  const importReviewBundleInputRef = useRef<HTMLInputElement | null>(null);

  const filteredLibrary = useMemo(() => {
    switch (libraryFilter) {
      case 'needs':
        return libraryEntries.filter((entry) => !entry.is_archived && entry.needs_review);
      case 'reviewed':
        return libraryEntries.filter((entry) => !entry.is_archived && !entry.needs_review);
      case 'archived':
        return libraryEntries.filter((entry) => entry.is_archived);
      case 'all':
      default:
        return libraryEntries.filter((entry) => !entry.is_archived);
    }
  }, [libraryEntries, libraryFilter]);

  const filteredLibraryWithSearch = useMemo(() => {
    const query = librarySearch.trim().toLowerCase();
    if (!query) return filteredLibrary;
    return filteredLibrary.filter((entry) => entry.title.toLowerCase().includes(query));
  }, [filteredLibrary, librarySearch]);

  const showSelectionControls = isLibraryHovering || selectedLibraryIds.size > 0;
  const allFilteredSelected =
    filteredLibraryWithSearch.length > 0 &&
    filteredLibraryWithSearch.every((entry) => selectedLibraryIds.has(entry.id));

  async function runBulkArchive(archived: boolean) {
    const ids = Array.from(selectedLibraryIds);
    if (ids.length === 0) return;
    await onBulkArchive(archived, ids);
    setSelectedLibraryIds(new Set());
  }

  async function runBulkRerun() {
    const targets = filteredLibraryWithSearch.filter(
      (entry) => selectedLibraryIds.has(entry.id) && Boolean(entry.latest_version_id),
    );
    if (targets.length === 0) return;
    await onBulkRerun(targets);
    setSelectedLibraryIds(new Set());
  }

  async function runBulkDelete() {
    const ids = Array.from(selectedLibraryIds);
    if (ids.length === 0) return;
    await onBulkDelete(ids);
    setSelectedLibraryIds(new Set());
  }

  return (
    <div className="library-overlay">
      <div className="library-shell">
        <div className="library-header">
          <div>
            <div className="library-title">Review Ledger</div>
            <div className="library-sub">
              Saved reviews stay with each version. Run a new review only when you ask.
            </div>
          </div>
          <div className="library-actions">
            <button
              className="ghost-button"
              type="button"
              disabled={isBundleImporting}
              onClick={() => importReviewBundleInputRef.current?.click()}
            >
              {isBundleImporting ? 'Importing…' : 'Import Bundle'}
            </button>
            <input
              ref={importReviewBundleInputRef}
              type="file"
              accept="application/json,.json,application/zip,.zip"
              multiple
              hidden
              onChange={(event) => {
                if (event.target.files) {
                  void onImportBundle(event.target.files);
                }
                event.target.value = '';
              }}
            />
            <div className="library-filters">
              <button
                className={`filter-chip ${libraryFilter === 'all' ? 'active' : ''}`}
                type="button"
                onClick={() => setLibraryFilter('all')}
              >
                All
              </button>
              <button
                className={`filter-chip ${libraryFilter === 'needs' ? 'active' : ''}`}
                type="button"
                onClick={() => setLibraryFilter('needs')}
              >
                Needs Review
              </button>
              <button
                className={`filter-chip ${libraryFilter === 'reviewed' ? 'active' : ''}`}
                type="button"
                onClick={() => setLibraryFilter('reviewed')}
              >
                Reviewed
              </button>
              <button
                className={`filter-chip ${libraryFilter === 'archived' ? 'active' : ''}`}
                type="button"
                onClick={() => setLibraryFilter('archived')}
              >
                Archived
              </button>
            </div>
            <input
              className="library-search"
              placeholder="Search documents"
              value={librarySearch}
              onChange={(event) => setLibrarySearch(event.target.value)}
            />
          </div>
        </div>

        {(showSelectionControls || bulkProgress) && (
          <div className="bulk-bar">
            <label className="bulk-select-all">
              <input
                type="checkbox"
                checked={allFilteredSelected}
                disabled={bulkProgress !== null || !showSelectionControls}
                onChange={(event) => {
                  const next = new Set(selectedLibraryIds);
                  if (event.target.checked) {
                    for (const entry of filteredLibraryWithSearch) {
                      next.add(entry.id);
                    }
                  } else {
                    for (const entry of filteredLibraryWithSearch) {
                      next.delete(entry.id);
                    }
                  }
                  setSelectedLibraryIds(next);
                }}
              />
              Select all ({filteredLibraryWithSearch.length})
            </label>
            {bulkProgress && (
              <div className="bulk-progress">
                {bulkProgress.label} {bulkProgress.done}/{bulkProgress.total}
              </div>
            )}
            <div className="bulk-actions">
              <button
                className="ghost-button"
                type="button"
                disabled={selectedLibraryIds.size === 0 || bulkProgress !== null}
                onClick={() => void runBulkArchive(true)}
              >
                Archive Selected
              </button>
              <button
                className="ghost-button"
                type="button"
                disabled={selectedLibraryIds.size === 0 || bulkProgress !== null}
                onClick={() => void runBulkArchive(false)}
              >
                Restore Selected
              </button>
              <button
                className="ghost-button"
                type="button"
                disabled={selectedLibraryIds.size === 0 || bulkProgress !== null}
                onClick={() => void runBulkRerun()}
              >
                Re-run Selected
              </button>
              <button
                className="ghost-button danger-button"
                type="button"
                disabled={selectedLibraryIds.size === 0 || bulkProgress !== null}
                onClick={() => void runBulkDelete()}
              >
                Delete Selected
              </button>
            </div>
          </div>
        )}

        <div
          className="library-grid"
          onMouseEnter={() => setIsLibraryHovering(true)}
          onMouseLeave={() => setIsLibraryHovering(false)}
        >
          {filteredLibraryWithSearch.length === 0 && (
            <div className="subtle">No documents yet.</div>
          )}
          {filteredLibraryWithSearch.map((entry) => {
            const statusLabel = entry.is_archived
              ? 'Archived'
              : entry.needs_review
                ? 'Needs Review'
                : 'Reviewed';
            const versionLabel = entry.latest_version_label ?? 'No versions yet';
            const lastEdited = entry.latest_version_created_at
              ? new Date(entry.latest_version_created_at).toLocaleString()
              : '—';
            const lastReviewed = entry.latest_review_completed_at
              ? new Date(entry.latest_review_completed_at).toLocaleString()
              : '—';
            return (
              <div key={entry.id} className={`library-card ${entry.needs_review ? 'needs' : 'ready'}`}>
                <div className="review-ribbon" />
                <div className="library-card-body">
                  <button
                    className="library-delete-btn"
                    type="button"
                    disabled={bulkProgress !== null}
                    onClick={() => void onDeleteDocument(entry.id, entry.title)}
                    aria-label={`Delete ${entry.title}`}
                  >
                    ×
                  </button>
                  <label className={`library-select ${showSelectionControls ? 'visible' : ''}`}>
                    <input
                      type="checkbox"
                      checked={selectedLibraryIds.has(entry.id)}
                      disabled={bulkProgress !== null || !showSelectionControls}
                      onChange={(event) => {
                        const next = new Set(selectedLibraryIds);
                        if (event.target.checked) {
                          next.add(entry.id);
                        } else {
                          next.delete(entry.id);
                        }
                        setSelectedLibraryIds(next);
                      }}
                    />
                  </label>
                  <div className="library-card-summary">
                    <div className="library-card-title">{entry.title}</div>
                    <div className="library-card-meta">
                      <span
                        className={`status-pill ${
                          entry.is_archived ? 'neutral' : entry.needs_review ? 'warn' : 'ok'
                        }`}
                      >
                        {statusLabel}
                      </span>
                    </div>
                  </div>
                  <div className="library-card-detail">
                    <div className="library-card-meta">
                      <span className="meta-pill">{versionLabel}</span>
                    </div>
                    <div className="library-timeline">
                      <div>
                        <div className="timeline-label">Last edit</div>
                        <div className="timeline-value">{lastEdited}</div>
                      </div>
                      <div>
                        <div className="timeline-label">Last review</div>
                        <div className="timeline-value">{lastReviewed}</div>
                      </div>
                    </div>
                    <div className="library-card-actions">
                      <button
                        className="ghost-button"
                        type="button"
                        onClick={() => {
                          router.push(`/?doc=${entry.id}`);
                        }}
                      >
                        Open
                      </button>
                      <button
                        className="primary-button"
                        type="button"
                        disabled={!entry.latest_version_id}
                        onClick={() => {
                          if (!entry.latest_version_id) return;
                          router.push(`/?doc=${entry.id}&run=1`);
                        }}
                      >
                        Run Review
                      </button>
                      <button
                        className="ghost-button"
                        type="button"
                        disabled={!entry.latest_version_id}
                        onClick={() => {
                          if (!entry.latest_version_id) return;
                          const confirmed = window.confirm(
                            `Start a new review run for "${entry.title}"?`,
                          );
                          if (!confirmed) return;
                          router.push(`/?doc=${entry.id}&run=1`);
                        }}
                      >
                        Re-run
                      </button>
                      <button
                        className="ghost-button"
                        type="button"
                        onClick={() => void onSetArchived(entry.id, !entry.is_archived)}
                      >
                        {entry.is_archived ? 'Restore' : 'Archive'}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default LibraryPanel;
