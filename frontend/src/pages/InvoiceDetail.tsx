import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { Attachment, Invoice, ShareLink } from '../api/types'
import { Alert, Button, Card, Spinner, StatusBadge } from '../components/ui'
import { formatDate, formatDateTime, formatMoney } from '../lib/format'

export function InvoiceDetail() {
  const { id } = useParams<{ id: string }>()
  const [invoice, setInvoice] = useState<Invoice | null>(null)
  const [share, setShare] = useState<ShareLink | null>(null)
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)

  const load = useCallback(async () => {
    if (!id) return
    try {
      const [detail, files] = await Promise.all([
        api.get<Invoice>(`/invoices/${id}`),
        api.get<Attachment[]>('/files'),
      ])
      setInvoice(detail)
      setAttachments(files.filter((file) => file.invoice_id === id))
      if (detail.share_token) {
        setShare({ token: detail.share_token, path: `/invoice/${detail.share_token}`, expires_at: detail.share_expires_at })
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not load this invoice.')
    }
  }, [id])

  useEffect(() => {
    void load()
  }, [load])

  async function run(action: () => Promise<unknown>, message: string) {
    setBusy(true)
    setError(null)
    try {
      await action()
      setNotice(message)
      await load()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'That action could not be completed.')
    } finally {
      setBusy(false)
    }
  }

  async function handleUpload(file: File) {
    const body = new FormData()
    body.append('file', file)
    if (id) body.append('invoice_id', id)
    await run(() => api.upload('/files/upload', body), 'Attachment uploaded.')
  }

  if (!invoice) {
    return error ? <Alert tone="error">{error}</Alert> : <Spinner label="Loading invoice" />
  }

  const shareUrl = share ? `${window.location.origin}${share.path}` : null
  const sharePath = share?.path ?? ''
  const shareExpiresAt = share?.expires_at ?? null

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <Link to="/invoices" className="text-xs text-muted hover:text-white">
            ← All invoices
          </Link>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight text-white">{invoice.number}</h1>
            <StatusBadge status={invoice.status} />
          </div>
          <p className="mt-1.5 text-sm text-muted">
            {invoice.client.name}
            {invoice.client.company ? ` · ${invoice.client.company}` : ''}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          {invoice.status === 'draft' ? (
            <Button disabled={busy} onClick={() => run(() => api.post(`/invoices/${invoice.id}/send`), 'Invoice sent.')}>
              Send invoice
            </Button>
          ) : null}
          {invoice.status === 'sent' ? (
            <Button
              disabled={busy}
              onClick={() => run(() => api.post(`/invoices/${invoice.id}/mark-paid`), 'Marked as paid.')}
            >
              Mark as paid
            </Button>
          ) : null}
          {invoice.status !== 'paid' && invoice.status !== 'void' ? (
            <Button
              variant="ghost"
              disabled={busy}
              onClick={() => run(() => api.post(`/invoices/${invoice.id}/void`), 'Invoice voided.')}
            >
              Void
            </Button>
          ) : null}
          <Button
            variant="ghost"
            disabled={busy}
            onClick={() => run(() => api.post(`/invoices/${invoice.id}/share`), 'Share link rotated.')}
          >
            {share ? 'Rotate link' : 'Create link'}
          </Button>
        </div>
      </header>

      {error ? <Alert tone="error">{error}</Alert> : null}
      {notice ? <Alert tone="success">{notice}</Alert> : null}

      <div className="grid gap-6 lg:grid-cols-[1fr_18rem] lg:items-start">
        <Card className="overflow-x-auto p-0">
          <div className="border-b border-line px-5 py-4">
            <h2 className="text-sm font-semibold text-white">Line items</h2>
          </div>
          <table className="w-full min-w-[34rem] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
                <th className="px-5 py-3 font-medium">Description</th>
                <th className="px-5 py-3 text-right font-medium">Qty</th>
                <th className="px-5 py-3 text-right font-medium">Unit</th>
                <th className="px-5 py-3 text-right font-medium">Amount</th>
              </tr>
            </thead>
            <tbody>
              {invoice.items.map((item) => (
                <tr key={item.id} className="border-b border-line/60 last:border-0">
                  <td className="px-5 py-3.5 text-slate-200">{item.description}</td>
                  <td className="px-5 py-3.5 text-right text-slate-300">{item.quantity}</td>
                  <td className="px-5 py-3.5 text-right text-slate-300">
                    {formatMoney(item.unit_price_cents, invoice.currency)}
                  </td>
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
            <div className="mt-1 flex justify-between border-t border-line pt-3 text-base font-semibold text-white">
              <dt>Total</dt>
              <dd>{formatMoney(invoice.total_cents, invoice.currency)}</dd>
            </div>
          </dl>
        </Card>

        <div className="flex flex-col gap-4">
          <Card>
            <h2 className="text-sm font-semibold text-white">Details</h2>
            <dl className="mt-3 flex flex-col gap-2 text-sm">
              <div className="flex justify-between gap-3">
                <dt className="text-muted">Issued</dt>
                <dd className="text-slate-200">{formatDate(invoice.issue_date)}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-muted">Due</dt>
                <dd className="text-slate-200">{formatDate(invoice.due_date)}</dd>
              </div>
              {invoice.paid_at ? (
                <div className="flex justify-between gap-3">
                  <dt className="text-muted">Paid</dt>
                  <dd className="text-slate-200">{formatDateTime(invoice.paid_at)}</dd>
                </div>
              ) : null}
            </dl>
            {invoice.notes ? (
              <p className="mt-4 border-t border-line pt-3 text-xs leading-relaxed text-muted">{invoice.notes}</p>
            ) : null}
          </Card>

          <Card>
            <h2 className="text-sm font-semibold text-white">Client link</h2>
            {shareUrl ? (
              <>
                <p className="mt-2 break-all rounded-lg border border-line bg-canvas px-3 py-2 text-xs text-slate-300">
                  {shareUrl}
                </p>
                <div className="mt-3 flex gap-2">
                  <Button
                    variant="ghost"
                    className="flex-1"
                    onClick={() => navigator.clipboard?.writeText(shareUrl)}
                  >
                    Copy link
                  </Button>
                  <a href={sharePath} target="_blank" rel="noreferrer" className="btn-ghost flex-1">
                    Open
                  </a>
                </div>
                {shareExpiresAt ? (
                  <p className="mt-2 text-xs text-muted">Expires {formatDateTime(shareExpiresAt)}</p>
                ) : null}
              </>
            ) : (
              <p className="mt-2 text-xs text-muted">
                No link yet. Sending the invoice creates one automatically.
              </p>
            )}
          </Card>

          <Card>
            <h2 className="text-sm font-semibold text-white">Attachments</h2>
            {attachments.length > 0 ? (
              <ul className="mt-3 flex flex-col gap-2">
                {attachments.map((file) => (
                  <li key={file.id} className="flex items-center justify-between gap-2 text-xs">
                    <a
                      href={`${import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api'}${file.download_path.replace('/api', '')}`}
                      className="truncate text-brand-soft hover:text-white"
                    >
                      {file.original_name}
                    </a>
                    <span className="text-muted">{Math.round(file.size_bytes / 1024)} KB</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-xs text-muted">PNG, JPEG or WebP up to 2 MB.</p>
            )}
            <input
              ref={fileInput}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0]
                if (file) void handleUpload(file)
                event.target.value = ''
              }}
            />
            <Button variant="ghost" className="mt-3 w-full" onClick={() => fileInput.current?.click()}>
              Upload attachment
            </Button>
          </Card>
        </div>
      </div>
    </div>
  )
}
