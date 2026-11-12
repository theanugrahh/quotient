import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from '../api/client'
import type { AdminStats, AdminUser, AuditEvent, Paged } from '../api/types'
import { Alert, Button, Card, Spinner, StatCard } from '../components/ui'
import { formatDateTime, formatMoney } from '../lib/format'

export function Admin() {
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [users, setUsers] = useState<Paged<AdminUser> | null>(null)
  const [audit, setAudit] = useState<Paged<AuditEvent> | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      const [summary, userPage, auditPage] = await Promise.all([
        api.get<AdminStats>('/admin/stats'),
        api.get<Paged<AdminUser>>('/admin/users'),
        api.get<Paged<AuditEvent>>('/admin/audit?page_size=15'),
      ])
      setStats(summary)
      setUsers(userPage)
      setAudit(auditPage)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not load the admin console.')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  async function act(action: () => Promise<unknown>) {
    setBusy(true)
    setError(null)
    try {
      await action()
      await load()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'That action could not be completed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-white">Admin console</h1>
        <p className="mt-1.5 text-sm text-muted">Workspace accounts, activity and recent system events.</p>
      </header>

      {error ? <Alert tone="error">{error}</Alert> : null}

      {stats ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Accounts" value={String(stats.users)} hint={`${stats.active_users} active`} />
          <StatCard label="Administrators" value={String(stats.admins)} hint="With elevated access" />
          <StatCard label="Invoices" value={String(stats.invoices)} hint={`${stats.paid_invoices} paid`} />
          <StatCard
            label="Collected"
            value={formatMoney(stats.gross_collected_cents)}
            hint="Across all accounts"
          />
        </div>
      ) : null}

      <Card className="overflow-x-auto p-0">
        <div className="border-b border-line px-5 py-4">
          <h2 className="text-sm font-semibold text-white">Accounts</h2>
        </div>
        {!users ? (
          <Spinner />
        ) : (
          <table className="w-full min-w-[40rem] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
                <th className="px-5 py-3 font-medium">Account</th>
                <th className="px-5 py-3 font-medium">Role</th>
                <th className="px-5 py-3 font-medium">Plan</th>
                <th className="px-5 py-3 font-medium">State</th>
                <th className="px-5 py-3 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.items.map((account) => (
                <tr key={account.id} className="border-b border-line/60 last:border-0">
                  <td className="px-5 py-3.5">
                    <p className="font-medium text-white">{account.name}</p>
                    <p className="text-xs text-muted">{account.email}</p>
                  </td>
                  <td className="px-5 py-3.5 capitalize text-slate-300">{account.role}</td>
                  <td className="px-5 py-3.5 capitalize text-slate-300">{account.plan}</td>
                  <td className="px-5 py-3.5">
                    <span
                      className={`chip ${
                        account.is_active
                          ? 'border-positive/40 bg-positive/10 text-positive'
                          : 'border-danger/40 bg-danger/10 text-danger'
                      }`}
                    >
                      {account.is_active ? 'Active' : 'Disabled'}
                    </span>
                  </td>
                  <td className="px-5 py-3.5">
                    <div className="flex justify-end gap-2">
                      <Button
                        variant="quiet"
                        disabled={busy}
                        onClick={() =>
                          act(() =>
                            api.patch(`/admin/users/${account.id}/role`, {
                              role: account.role === 'admin' ? 'user' : 'admin',
                            }),
                          )
                        }
                      >
                        {account.role === 'admin' ? 'Make user' : 'Make admin'}
                      </Button>
                      <Button
                        variant="quiet"
                        disabled={busy}
                        onClick={() =>
                          act(() =>
                            api.post(
                              `/admin/users/${account.id}/${account.is_active ? 'deactivate' : 'activate'}`,
                            ),
                          )
                        }
                      >
                        {account.is_active ? 'Disable' : 'Enable'}
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card className="overflow-x-auto p-0">
        <div className="border-b border-line px-5 py-4">
          <h2 className="text-sm font-semibold text-white">Audit trail</h2>
        </div>
        {!audit ? (
          <Spinner />
        ) : (
          <table className="w-full min-w-[34rem] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
                <th className="px-5 py-3 font-medium">When</th>
                <th className="px-5 py-3 font-medium">Action</th>
                <th className="px-5 py-3 font-medium">Entity</th>
                <th className="px-5 py-3 font-medium">Source</th>
              </tr>
            </thead>
            <tbody>
              {audit.items.map((event) => (
                <tr key={event.id} className="border-b border-line/60 last:border-0">
                  <td className="px-5 py-3.5 text-slate-300">{formatDateTime(event.created_at)}</td>
                  <td className="px-5 py-3.5 font-mono text-xs text-brand-soft">{event.action}</td>
                  <td className="px-5 py-3.5 text-slate-300">
                    {event.entity_type}
                    {event.entity_id ? ` · ${event.entity_id.slice(0, 8)}` : ''}
                  </td>
                  <td className="px-5 py-3.5 text-muted">{event.ip_address ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}
