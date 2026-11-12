import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import type { InvoiceStatus, Paged, InvoiceSummary } from '../api/types'
import { Card, EmptyState, Spinner, StatusBadge } from '../components/ui'
import { formatDate, formatMoney } from '../lib/format'

const filters: { value: string; label: string }[] = [
  { value: '', label: 'All' },
  { value: 'draft', label: 'Draft' },
  { value: 'sent', label: 'Sent' },
  { value: 'paid', label: 'Paid' },
  { value: 'void', label: 'Void' },
]

export function Invoices() {
  const [searchParams, setSearchParams] = useSearchParams()
  const status = searchParams.get('status') ?? ''
  const [page, setPage] = useState<Paged<InvoiceSummary> | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const query = status ? `?status=${status}` : ''
      setPage(await api.get<Paged<InvoiceSummary>>(`/invoices${query}`))
    } finally {
      setLoading(false)
    }
  }, [status])

  useEffect(() => {
    void load()
  }, [load])

  function selectStatus(value: string) {
    const next = new URLSearchParams(searchParams)
    if (value) {
      next.set('status', value)
    } else {
      next.delete('status')
    }
    setSearchParams(next)
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">Invoices</h1>
          <p className="mt-1.5 text-sm text-muted">Every quote, invoice and receipt you have created.</p>
        </div>
        <Link to="/invoices/new" className="btn-primary">
          New invoice
        </Link>
      </header>

      <div className="flex flex-wrap gap-2">
        {filters.map((filter) => (
          <button
            key={filter.value}
            type="button"
            onClick={() => selectStatus(filter.value)}
            className={`chip transition ${
              status === filter.value
                ? 'border-brand/50 bg-brand/15 text-brand-soft'
                : 'border-line text-muted hover:text-white'
            }`}
          >
            {filter.label}
          </button>
        ))}
      </div>

      {loading ? (
        <Spinner label="Loading invoices" />
      ) : page && page.items.length > 0 ? (
        <Card className="overflow-x-auto p-0">
          <table className="w-full min-w-[42rem] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
                <th className="px-5 py-3 font-medium">Invoice</th>
                <th className="px-5 py-3 font-medium">Client</th>
                <th className="px-5 py-3 font-medium">Issued</th>
                <th className="px-5 py-3 font-medium">Due</th>
                <th className="px-5 py-3 font-medium">Status</th>
                <th className="px-5 py-3 text-right font-medium">Total</th>
              </tr>
            </thead>
            <tbody>
              {page.items.map((invoice) => (
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
                  <td className="px-5 py-3.5 text-slate-300">{formatDate(invoice.due_date)}</td>
                  <td className="px-5 py-3.5">
                    <StatusBadge status={invoice.status as InvoiceStatus} />
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
          title={status ? `No ${status} invoices` : 'No invoices yet'}
          body={
            status
              ? 'Try a different filter to see more of your work.'
              : 'Create your first invoice and it will show up here straight away.'
          }
          action={
            !status ? (
              <Link to="/invoices/new" className="btn-primary">
                Create an invoice
              </Link>
            ) : undefined
          }
        />
      )}
    </div>
  )
}
