'use client';

import React, { useEffect, useMemo, useState } from 'react';

import { apiFetch } from '../../src/lib/api';
import {
  AdminOverview,
  AdminUserRead,
  DocumentLibraryEntry,
  DocumentPermissionRead
} from '../../src/lib/types';

function normalizeError(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  return 'Unexpected error';
}

type AdminPanelProps = {
  libraryEntries: DocumentLibraryEntry[];
  onStatus: (message: string | null) => void;
  onError: (message: string | null) => void;
};

export function AdminPanel({ libraryEntries, onStatus, onError }: AdminPanelProps) {
  const [adminOverview, setAdminOverview] = useState<AdminOverview | null>(null);
  const [adminUsers, setAdminUsers] = useState<AdminUserRead[]>([]);
  const [adminPermissions, setAdminPermissions] = useState<DocumentPermissionRead[]>([]);
  const [selectedPermissionDocumentId, setSelectedPermissionDocumentId] = useState<number | null>(null);
  const [newAdminUser, setNewAdminUser] = useState({
    name: '',
    email: '',
    role: 'default' as 'admin' | 'default'
  });
  const [newPermission, setNewPermission] = useState({
    user_id: 0,
    permission_level: 'viewer' as 'owner' | 'editor' | 'viewer'
  });

  async function loadAdminOverview() {
    try {
      const data = await apiFetch<AdminOverview>('/admin/overview');
      setAdminOverview(data);
    } catch (error) {
      onError(normalizeError(error));
    }
  }

  async function loadAdminUsers() {
    try {
      const users = await apiFetch<AdminUserRead[]>('/admin/users');
      const safeUsers = Array.isArray(users) ? users : [];
      setAdminUsers(safeUsers);
      if (safeUsers.length > 0 && newPermission.user_id === 0) {
        setNewPermission((prev) => ({ ...prev, user_id: safeUsers[0].id }));
      }
    } catch (error) {
      onError(normalizeError(error));
    }
  }

  async function loadAdminPermissions() {
    try {
      const permissions = await apiFetch<DocumentPermissionRead[]>('/admin/permissions');
      setAdminPermissions(Array.isArray(permissions) ? permissions : []);
    } catch (error) {
      onError(normalizeError(error));
    }
  }

  async function refreshAdminData() {
    await Promise.all([loadAdminOverview(), loadAdminUsers(), loadAdminPermissions()]);
  }

  useEffect(() => {
    void refreshAdminData();
    // Refresh on mount. onStatus/onError identities may change but we
    // intentionally only fetch once per panel mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const visibleAdminPermissions = useMemo(() => {
    if (!selectedPermissionDocumentId) return adminPermissions;
    return adminPermissions.filter((perm) => perm.document_id === selectedPermissionDocumentId);
  }, [adminPermissions, selectedPermissionDocumentId]);

  async function handleCreateAdminUser() {
    if (!newAdminUser.name.trim() || !newAdminUser.email.trim()) {
      onError('User name and email are required.');
      return;
    }
    try {
      await apiFetch<AdminUserRead>('/admin/users', {
        method: 'POST',
        body: JSON.stringify({
          name: newAdminUser.name.trim(),
          email: newAdminUser.email.trim(),
          role: newAdminUser.role,
          is_active: true
        })
      });
      setNewAdminUser({ name: '', email: '', role: 'default' });
      onStatus('User created.');
      await refreshAdminData();
    } catch (error) {
      onError(normalizeError(error));
    }
  }

  async function handleUpdateAdminUser(
    userId: number,
    patch: Partial<{ role: 'admin' | 'default'; is_active: boolean }>
  ) {
    try {
      await apiFetch<AdminUserRead>(`/admin/users/${userId}`, {
        method: 'PATCH',
        body: JSON.stringify(patch)
      });
      await refreshAdminData();
    } catch (error) {
      onError(normalizeError(error));
    }
  }

  async function handleDeleteAdminUser(userId: number) {
    const confirmed = window.confirm('Delete this user and all document permissions?');
    if (!confirmed) return;
    try {
      await apiFetch<null>(`/admin/users/${userId}`, { method: 'DELETE' });
      onStatus('User deleted.');
      await refreshAdminData();
    } catch (error) {
      onError(normalizeError(error));
    }
  }

  async function handleCreatePermission() {
    if (!selectedPermissionDocumentId || newPermission.user_id <= 0) {
      onError('Select a document and user before adding permission.');
      return;
    }
    try {
      await apiFetch<DocumentPermissionRead>('/admin/permissions', {
        method: 'POST',
        body: JSON.stringify({
          document_id: selectedPermissionDocumentId,
          user_id: newPermission.user_id,
          permission_level: newPermission.permission_level
        })
      });
      onStatus('Permission upserted.');
      await refreshAdminData();
    } catch (error) {
      onError(normalizeError(error));
    }
  }

  async function handleUpdatePermission(
    permissionId: number,
    permission_level: 'owner' | 'editor' | 'viewer'
  ) {
    try {
      await apiFetch<DocumentPermissionRead>(`/admin/permissions/${permissionId}`, {
        method: 'PATCH',
        body: JSON.stringify({ permission_level })
      });
      await refreshAdminData();
    } catch (error) {
      onError(normalizeError(error));
    }
  }

  async function handleDeletePermission(permissionId: number) {
    try {
      await apiFetch<null>(`/admin/permissions/${permissionId}`, { method: 'DELETE' });
      await refreshAdminData();
    } catch (error) {
      onError(normalizeError(error));
    }
  }

  return (
    <div className="admin-overlay">
      <div className="admin-shell">
        <div className="admin-header">
          <div>
            <div className="library-title">Administrator</div>
            <div className="library-sub">
              Repository visibility, user access control, document permissions, and review operations.
            </div>
          </div>
          <button className="ghost-button" type="button" onClick={() => void refreshAdminData()}>
            Refresh
          </button>
        </div>

        <div className="admin-grid">
          <section className="admin-card">
            <div className="drawer-title">Repository</div>
            <div className="admin-kv">Enabled: {adminOverview?.repository.enabled ? 'Yes' : 'No'}</div>
            <div className="admin-kv">Root: {adminOverview?.repository.root ?? '—'}</div>
            <div className="admin-kv">Tenant Repo Path: {adminOverview?.repository.tenant_root ?? '—'}</div>
            <div className="admin-kv">
              Repositories: {adminOverview?.repository.repository_count ?? 0}
            </div>
          </section>

          <section className="admin-card">
            <div className="drawer-title">Summary</div>
            <div className="admin-stats">
              <div className="stat">
                <div className="stat-label">Users</div>
                <div className="stat-value">{adminOverview?.users.total ?? 0}</div>
              </div>
              <div className="stat">
                <div className="stat-label">Admins</div>
                <div className="stat-value">{adminOverview?.users.admins ?? 0}</div>
              </div>
              <div className="stat">
                <div className="stat-label">Documents</div>
                <div className="stat-value">{adminOverview?.documents.total ?? 0}</div>
              </div>
              <div className="stat">
                <div className="stat-label">In Progress Jobs</div>
                <div className="stat-value">{adminOverview?.jobs.in_progress ?? 0}</div>
              </div>
            </div>
          </section>

          <section className="admin-card wide">
            <div className="drawer-title">Work In Progress</div>
            <div className="history-list">
              {(adminOverview?.in_progress_jobs ?? []).length === 0 && (
                <div className="subtle">No jobs currently running.</div>
              )}
              {(adminOverview?.in_progress_jobs ?? []).map((job) => (
                <div key={job.id} className="history-item">
                  <div>
                    <div className="history-msg">
                      #{job.id} {job.status} · {job.document_title}
                    </div>
                    <div className="history-time">
                      {new Date(job.created_at).toLocaleString()} · {job.provider}/{job.model}
                    </div>
                  </div>
                  <span className="pill">{job.trigger}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="admin-card wide">
            <div className="drawer-title">Historical Jobs</div>
            <div className="history-list">
              {(adminOverview?.recent_jobs ?? []).length === 0 && (
                <div className="subtle">No jobs yet.</div>
              )}
              {(adminOverview?.recent_jobs ?? []).slice(0, 20).map((job) => (
                <div key={job.id} className="history-item">
                  <div>
                    <div className="history-msg">
                      #{job.id} {job.status} · {job.document_title}
                    </div>
                    <div className="history-time">
                      {new Date(job.created_at).toLocaleString()}
                      {job.completed_at ? ` · completed ${new Date(job.completed_at).toLocaleString()}` : ''}
                    </div>
                  </div>
                  <span className="pill">
                    {job.provider}/{job.model}
                  </span>
                </div>
              ))}
            </div>
          </section>

          <section className="admin-card">
            <div className="drawer-title">Users</div>
            <div className="admin-user-create">
              <input
                className="input"
                placeholder="Name"
                value={newAdminUser.name}
                onChange={(event) =>
                  setNewAdminUser((prev) => ({ ...prev, name: event.target.value }))
                }
              />
              <input
                className="input"
                placeholder="Email"
                value={newAdminUser.email}
                onChange={(event) =>
                  setNewAdminUser((prev) => ({ ...prev, email: event.target.value }))
                }
              />
              <select
                className="input"
                value={newAdminUser.role}
                onChange={(event) =>
                  setNewAdminUser((prev) => ({
                    ...prev,
                    role: event.target.value as 'admin' | 'default'
                  }))
                }
              >
                <option value="default">Default</option>
                <option value="admin">Admin</option>
              </select>
              <button className="primary-button" type="button" onClick={() => void handleCreateAdminUser()}>
                Add User
              </button>
            </div>
            <div className="history-list">
              {adminUsers.map((user) => (
                <div key={user.id} className="history-item">
                  <div>
                    <div className="history-msg">
                      {user.name} · {user.email}
                    </div>
                    <div className="history-time">Created {new Date(user.created_at).toLocaleString()}</div>
                  </div>
                  <div className="admin-user-actions">
                    <select
                      className="input compact"
                      value={user.role}
                      onChange={(event) =>
                        void handleUpdateAdminUser(user.id, {
                          role: event.target.value as 'admin' | 'default'
                        })
                      }
                    >
                      <option value="default">default</option>
                      <option value="admin">admin</option>
                    </select>
                    <button
                      className="ghost-button"
                      type="button"
                      onClick={() =>
                        void handleUpdateAdminUser(user.id, {
                          is_active: !user.is_active
                        })
                      }
                    >
                      {user.is_active ? 'Disable' : 'Enable'}
                    </button>
                    <button
                      className="ghost-button danger-button"
                      type="button"
                      onClick={() => void handleDeleteAdminUser(user.id)}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="admin-card">
            <div className="drawer-title">Document Permissions</div>
            <select
              className="input"
              value={selectedPermissionDocumentId ?? ''}
              onChange={(event) => {
                const rawValue = event.target.value;
                if (!rawValue) {
                  setSelectedPermissionDocumentId(null);
                  return;
                }
                const value = Number(rawValue);
                setSelectedPermissionDocumentId(Number.isFinite(value) ? value : null);
              }}
            >
              <option value="">Select document</option>
              {libraryEntries.map((entry) => (
                <option key={entry.id} value={entry.id}>
                  {entry.title}
                </option>
              ))}
            </select>
            <div className="spacer" />
            <div className="admin-user-create">
              <select
                className="input"
                value={newPermission.user_id}
                onChange={(event) =>
                  setNewPermission((prev) => ({
                    ...prev,
                    user_id: Number(event.target.value)
                  }))
                }
              >
                <option value={0}>Select user</option>
                {adminUsers.map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.name} ({user.email})
                  </option>
                ))}
              </select>
              <select
                className="input"
                value={newPermission.permission_level}
                onChange={(event) =>
                  setNewPermission((prev) => ({
                    ...prev,
                    permission_level: event.target.value as 'owner' | 'editor' | 'viewer'
                  }))
                }
              >
                <option value="viewer">viewer</option>
                <option value="editor">editor</option>
                <option value="owner">owner</option>
              </select>
              <button className="primary-button" type="button" onClick={() => void handleCreatePermission()}>
                Grant/Update
              </button>
            </div>
            <div className="history-list">
              {visibleAdminPermissions.map((perm) => (
                <div key={perm.id} className="history-item">
                  <div>
                    <div className="history-msg">
                      {perm.user_name} · {perm.user_email}
                    </div>
                    <div className="history-time">Added {new Date(perm.created_at).toLocaleString()}</div>
                  </div>
                  <div className="admin-user-actions">
                    <select
                      className="input compact"
                      value={perm.permission_level}
                      onChange={(event) =>
                        void handleUpdatePermission(
                          perm.id,
                          event.target.value as 'owner' | 'editor' | 'viewer'
                        )
                      }
                    >
                      <option value="viewer">viewer</option>
                      <option value="editor">editor</option>
                      <option value="owner">owner</option>
                    </select>
                    <button
                      className="ghost-button danger-button"
                      type="button"
                      onClick={() => void handleDeletePermission(perm.id)}
                    >
                      Remove
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="admin-card wide">
            <div className="drawer-title">Permission Matrix</div>
            {adminUsers.length === 0 || libraryEntries.length === 0 ? (
              <div className="subtle">Add users and documents to view matrix.</div>
            ) : (
              <div className="admin-matrix-wrap">
                <table className="admin-matrix">
                  <thead>
                    <tr>
                      <th>User</th>
                      {libraryEntries.slice(0, 8).map((entry) => (
                        <th key={`head-${entry.id}`}>{entry.title}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {adminUsers.map((user) => (
                      <tr key={`row-${user.id}`}>
                        <td>{user.name}</td>
                        {libraryEntries.slice(0, 8).map((entry) => {
                          const perm = adminPermissions.find(
                            (item) => item.user_id === user.id && item.document_id === entry.id
                          );
                          return (
                            <td key={`cell-${user.id}-${entry.id}`}>
                              <span className="meta-pill">{perm?.permission_level ?? '—'}</span>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="admin-card wide">
            <div className="drawer-title">Recent Admin Actions</div>
            <div className="history-list">
              {(adminOverview?.recent_actions ?? []).length === 0 && (
                <div className="subtle">No admin actions logged yet.</div>
              )}
              {(adminOverview?.recent_actions ?? []).map((action) => (
                <div key={action.id} className="history-item">
                  <div>
                    <div className="history-msg">
                      {action.action} · {action.target_type}
                      {action.target_id ? ` #${action.target_id}` : ''}
                    </div>
                    <div className="history-time">
                      {action.actor_email ?? 'unknown'} ·{' '}
                      {new Date(action.created_at).toLocaleString()}
                    </div>
                  </div>
                  <span className="pill">{action.details ?? ''}</span>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

export default AdminPanel;
