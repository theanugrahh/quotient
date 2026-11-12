import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { DashboardStats, Paged, InvoiceSummary } from '../api/types'
import { Button, Card, EmptyState, Spinner, StatCard, StatusBadge } from '../components/ui'
import { formatDate, formatMoney } from '../lib/format'

export function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [recent, setRecent] = useState<Paged<InvoiceSummary> | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      const [summary, invoices] = await Promise.all([
        api.get<DashboardStats>('/invoices/stats/summary'),
        api.get<Paged<InvoiceSummary>>('/invoices?page_size=5'),
      ])
      setStats(summary)
      setRecent(invoices)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  if (loading) {
    return <Spinner label="Loading your dashboard" />
  }

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">Dashboard</h1>
          <p className="mt-1.5 text-sm text-muted">Where everything you have billed currently stands.</p>
        </div>
        <Link to="/invoices/new" className="btn-primary">
          New invoice
        </Link>
      </header>

      {stats ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Collected" value={formatMoney(stats.collected_cents, stats.currency)} hint="Paid invoices" />
          <StatCard
            label="Outstanding"
            value={formatMoney(stats.outstanding_cents, stats.currency)}
            hint="Sent and unpaid"
          />
          <StatCard label="Clients" value={String(stats.client_count)} hint="Active accounts" />
          <StatCard
            label="Invoices"
            value={String(stats.total_invoices)}
            hint={`${stats.draft_count} draft · ${stats.sent_count} sent · ${stats.paid_count} paid`}
          />
        </div>
      ) : null}

      <section className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">Recent invoices</h2>
          <Link to="/invoices" className="btn-quiet">
            View all
          </Link>
        </div>

        {recent && recent.items.length > 0 ? (
          <Card className="overflow-x-auto p-0">
            <table className="w-full min-w-[40rem] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
                  <th className="px-5 py-3 font-medium">Invoice</th>
                  <th className="px-5 py-3 font-medium">Client</th>
                  <th className="px-5 py-3 font-medium">Issued</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 text-right font-medium">Total</th>
                </tr>
              </thead>
              <tbody>
                {recent.items.map((invoice) => (
                  <tr key={invoice.id} className="border-b border-line/60 last:border-0">
                    <td className="px-5 py-3.5">
                      <Link to={`/invoices/${invoice.id}`} className="font-medium text-white hover:text-brand-soft">
                        {invoice.number}
                      </Link>
                    </td>
                    <td className="px-5 py-3.5 text-slate-300">
                      {invoice.client_name}
                      {invoice.client_company ? (
                        <span className="block text-xs text-muted">{invoice.client_company}</span>
                      ) : null}
                    </td>
                    <td className="px-5 py-3.5 text-slate-300">{formatDate(invoice.issue_date)}</td>
                    <td className="px-5 py-3.5">
                      <StatusBadge status={invoice.status} />
                    </td>
                    <td className="px-5 py-3.5 text-right font-medium text-white">
                      {formatMoney(invoice.total_cents, invoice.currency)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        ) : (
          <EmptyState
            title="No invoices yet"
            body="Once you send your first invoice it will show up here with its status and total."
            action={
              <Link to="/invoices/new" className="btn-primary">
                Create an invoice
              </Link>
            }
          />
        )}
      </section>

      {stats && stats.draft_count > 0 ? (
        <Card className="flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
          <div>
            <h3 className="text-sm font-semibold text-white">
              {stats.draft_count} {stats.draft_count === 1 ? 'draft is' : 'drafts are'} waiting
            </h3>
            <p className="mt-1 text-sm text-muted">Drafts are private until you send them.</p>
          </div>
          <Link to="/invoices?status=draft">
            <Button variant="ghost">Review drafts</Button>
          </Link>
        </Card>
      ) : null}
    </div>
  )
}
