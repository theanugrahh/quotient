import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { Client, Paged } from '../api/types'
import { Alert, Button, Card, Field, Input, Select, Spinner, Textarea } from '../components/ui'
import { formatMoney } from '../lib/format'

type DraftLine = {
  description: string
  quantity: string
  unitPrice: string
}

const blankLine = (): DraftLine => ({ description: '', quantity: '1', unitPrice: '' })

export function NewInvoice() {
  const navigate = useNavigate()
  const [clients, setClients] = useState<Paged<Client> | null>(null)
  const [clientId, setClientId] = useState('')
  const [lines, setLines] = useState<DraftLine[]>([blankLine()])
  const [taxRate, setTaxRate] = useState('0')
  const [discountRate, setDiscountRate] = useState('0')
  const [dueDate, setDueDate] = useState('')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api
      .get<Paged<Client>>('/clients')
      .then((page) => {
        setClients(page)
        if (page.items.length > 0) {
          setClientId(page.items[0].id)
        }
      })
      .catch(() => setError('Could not load your clients.'))
  }, [])

  const estimate = useMemo(() => {
    const subtotal = lines.reduce((total, line) => {
      const quantity = Number(line.quantity) || 0
      const unitPrice = Number(line.unitPrice) || 0
      return total + quantity * unitPrice
    }, 0)
    const discount = (subtotal * (Number(discountRate) || 0)) / 100
    const tax = ((subtotal - discount) * (Number(taxRate) || 0)) / 100
    return { subtotal, discount, tax, total: subtotal - discount + tax }
  }, [lines, taxRate, discountRate])

  function updateLine(index: number, patch: Partial<DraftLine>) {
    setLines((current) => current.map((line, position) => (position === index ? { ...line, ...patch } : line)))
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const invoice = await api.post<{ id: string }>('/invoices', {
        client_id: clientId,
        items: lines.map((line) => ({
          description: line.description,
          quantity: line.quantity,
          unit_price_cents: Math.round((Number(line.unitPrice) || 0) * 100),
        })),
        tax_rate_bp: Math.round((Number(taxRate) || 0) * 100),
        discount_bp: Math.round((Number(discountRate) || 0) * 100),
        currency: 'usd',
        notes,
        due_date: dueDate ? new Date(`${dueDate}T00:00:00Z`).toISOString() : null,
      })
      navigate(`/invoices/${invoice.id}`)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not create the invoice.')
    } finally {
      setBusy(false)
    }
  }

  if (!clients) {
    return <Spinner label="Preparing the form" />
  }

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-white">New invoice</h1>
        <p className="mt-1.5 text-sm text-muted">
          It starts as a draft. Nothing is visible to the client until you send it.
        </p>
      </header>

      {error ? <Alert tone="error">{error}</Alert> : null}

      {clients.items.length === 0 ? (
        <Alert tone="info">
          You need a client before you can raise an invoice.{' '}
          <a href="/clients" className="font-medium text-brand-soft underline">
            Add a client
          </a>
          .
        </Alert>
      ) : null}

      <form className="grid gap-6 lg:grid-cols-[1fr_18rem]" onSubmit={handleSubmit} noValidate>
        <div className="flex flex-col gap-6">
          <Card className="flex flex-col gap-4">
            <Field label="Client" htmlFor="client">
              <Select id="client" value={clientId} onChange={(event) => setClientId(event.target.value)} required>
                <option value="">Select a client</option>
                {clients.items.map((client) => (
                  <option key={client.id} value={client.id}>
                    {client.name}
                    {client.company ? ` · ${client.company}` : ''}
                  </option>
                ))}
              </Select>
            </Field>
          </Card>

          <Card>
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-white">Line items</h2>
              <Button type="button" variant="ghost" onClick={() => setLines((current) => [...current, blankLine()])}>
                Add line
              </Button>
            </div>

            <div className="mt-4 flex flex-col gap-3">
              {lines.map((line, index) => (
                <div key={index} className="grid gap-3 rounded-xl border border-line/70 p-3 sm:grid-cols-[1fr_6rem_8rem_auto]">
                  <Input
                    aria-label={`Description ${index + 1}`}
                    placeholder="Design retainer"
                    required
                    value={line.description}
                    onChange={(event) => updateLine(index, { description: event.target.value })}
                  />
                  <Input
                    aria-label={`Quantity ${index + 1}`}
                    type="number"
                    min="0.001"
                    step="0.001"
                    value={line.quantity}
                    onChange={(event) => updateLine(index, { quantity: event.target.value })}
                  />
                  <Input
                    aria-label={`Unit price ${index + 1}`}
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="0.00"
                    required
                    value={line.unitPrice}
                    onChange={(event) => updateLine(index, { unitPrice: event.target.value })}
                  />
                  <Button
                    type="button"
                    variant="quiet"
                    disabled={lines.length === 1}
                    onClick={() => setLines((current) => current.filter((_, position) => position !== index))}
                  >
                    Remove
                  </Button>
                </div>
              ))}
            </div>
          </Card>

          <Card className="flex flex-col gap-4">
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Tax rate" htmlFor="tax" hint="Percentage">
                <Input
                  id="tax"
                  type="number"
                  min="0"
                  max="100"
                  step="0.01"
                  value={taxRate}
                  onChange={(event) => setTaxRate(event.target.value)}
                />
              </Field>
              <Field label="Discount" htmlFor="discount" hint="Percentage">
                <Input
                  id="discount"
                  type="number"
                  min="0"
                  max="100"
                  step="0.01"
                  value={discountRate}
                  onChange={(event) => setDiscountRate(event.target.value)}
                />
              </Field>
              <Field label="Due date" htmlFor="due">
                <Input id="due" type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} />
              </Field>
            </div>
            <Field label="Notes for the client" htmlFor="notes">
              <Textarea
                id="notes"
                rows={3}
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                placeholder="Payment is due within 30 days. Thank you for your business."
              />
            </Field>
          </Card>
        </div>

        <Card className="h-fit">
          <h2 className="text-sm font-semibold text-white">Summary</h2>
          <dl className="mt-4 flex flex-col gap-2 text-sm">
            <div className="flex justify-between text-muted">
              <dt>Subtotal</dt>
              <dd>{formatMoney(Math.round(estimate.subtotal * 100))}</dd>
            </div>
            {estimate.discount > 0 ? (
              <div className="flex justify-between text-muted">
                <dt>Discount</dt>
                <dd>-{formatMoney(Math.round(estimate.discount * 100))}</dd>
              </div>
            ) : null}
            {estimate.tax > 0 ? (
              <div className="flex justify-between text-muted">
                <dt>Tax</dt>
                <dd>{formatMoney(Math.round(estimate.tax * 100))}</dd>
              </div>
            ) : null}
            <div className="mt-2 flex justify-between border-t border-line pt-3 text-base font-semibold text-white">
              <dt>Total</dt>
              <dd>{formatMoney(Math.round(estimate.total * 100))}</dd>
            </div>
          </dl>
          <p className="mt-3 text-xs text-muted">The server recalculates every total before saving.</p>
          <Button type="submit" className="mt-4 w-full" disabled={busy || clients.items.length === 0}>
            {busy ? 'Creating…' : 'Create draft'}
          </Button>
        </Card>
      </form>
    </div>
  )
}
