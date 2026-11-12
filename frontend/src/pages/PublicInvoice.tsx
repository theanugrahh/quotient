import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, apiUrl, ApiError } from '../api/client'
import type { PublicInvoice } from '../api/types'
import { Alert, Button, Card, Spinner, StatusBadge } from '../components/ui'
import { formatDate, formatMoney } from '../lib/format'

export function PublicInvoice() {
  const { token } = useParams<{ token: string }>()
  const [invoice, setInvoice] = useState<PublicInvoice | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!token) return
    api
      .get<PublicInvoice>(`/public/invoices/${token}`)
      .then(setInvoice)
      .catch((caught) =>
        setError(caught instanceof ApiError ? caught.message : 'This invoice link is not valid.'),
      )
  }, [token])

  async function pay() {
    if (!token) return
    setBusy(true)
    setError(null)
    try {
      const checkout = await api.post<{ url: string }>(`/public/invoices/${token}/checkout`)
      window.location.href = apiUrl(checkout.url)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not start the payment.')
      setBusy(false)
    }
  }

  if (error && !invoice) {
    return (
      <div className="mx-auto max-w-lg py-10">
        <Alert tone="error">{error}</Alert>
      </div>
    )
  }

  if (!invoice) {
    return <Spinner label="Loading invoice" />
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 py-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand text-sm font-bold text-white">Q</span>
            <p className="text-lg font-semibold text-white">{invoice.studio_name}</p>
          </div>
          <h1 className="mt-4 text-2xl font-semibold tracking-tight text-white">Invoice {invoice.number}</h1>
          <p className="mt-1 text-sm text-muted">
            Billed to {invoice.client_name}
            {invoice.client_company ? ` · ${invoice.client_company}` : ''}
          </p>
        </div>
        <StatusBadge status={invoice.status} />
      </header>

      {error ? <Alert tone="error">{error}</Alert> : null}

      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[30rem] text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
              <th className="px-5 py-3 font-medium">Description</th>
              <th className="px-5 py-3 text-right font-medium">Qty</th>
              <th className="px-5 py-3 text-right font-medium">Amount</th>
            </tr>
          </thead>
          <tbody>
            {invoice.items.map((item) => (
              <tr key={item.id} className="border-b border-line/60 last:border-0">
                <td className="px-5 py-3.5 text-slate-200">{item.description}</td>
                <td className="px-5 py-3.5 text-right text-slate-300">{item.quantity}</td>
                <td className="px-5 py-3.5 text-right font-medium text-white">
                  {formatMoney(item.amount_cents, invoice.currency)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <dl className="flex flex-col gap-2 border-t border-line px-5 py-4 text-sm">
          <div className="flex justify-between text-muted">
            <dt>Subtotal</dt>
            <dd>{formatMoney(invoice.subtotal_cents, invoice.currency)}</dd>
          </div>
          {invoice.discount_cents > 0 ? (
            <div className="flex justify-between text-muted">
              <dt>Discount</dt>
              <dd>-{formatMoney(invoice.discount_cents, invoice.currency)}</dd>
            </div>
          ) : null}
          {invoice.tax_cents > 0 ? (
            <div className="flex justify-between text-muted">
              <dt>Tax</dt>
              <dd>{formatMoney(invoice.tax_cents, invoice.currency)}</dd>
            </div>
          ) : null}
          <div className="mt-1 flex justify-between border-t border-line pt-3 text-lg font-semibold text-white">
            <dt>Total due</dt>
            <dd>{formatMoney(invoice.total_cents, invoice.currency)}</dd>
          </div>
        </dl>
      </Card>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs text-muted">
          Issued {formatDate(invoice.issue_date)}
          {invoice.due_date ? ` · Due ${formatDate(invoice.due_date)}` : ''}
        </p>
        {invoice.status === 'paid' ? (
          <span className="chip border-positive/40 bg-positive/10 text-positive">Paid in full</span>
        ) : (
          <Button onClick={pay} disabled={busy}>
            {busy ? 'Redirecting…' : `Pay ${formatMoney(invoice.total_cents, invoice.currency)}`}
          </Button>
        )}
      </div>

      {invoice.notes ? (
        <p className="border-t border-line pt-4 text-xs leading-relaxed text-muted">{invoice.notes}</p>
      ) : null}
    </div>
  )
}
