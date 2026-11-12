import { useCallback, useEffect, useState } from 'react'
import { api, ApiError, resolveTarget } from '../api/client'
import type { Payment, Plan } from '../api/types'
import { Alert, Button, Card, Spinner } from '../components/ui'
import { formatDateTime, formatMoney } from '../lib/format'

export function Billing() {
  const [plan, setPlan] = useState<Plan | null>(null)
  const [payments, setPayments] = useState<Payment[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      const [current, history] = await Promise.all([
        api.get<Plan>('/billing/plan'),
        api.get<Payment[]>('/billing/payments'),
      ])
      setPlan(current)
      setPayments(history)
    } catch {
      setError('Could not load your billing details.')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  async function startCheckout() {
    setBusy(true)
    setError(null)
    try {
      const checkout = await api.post<{ url: string }>('/billing/checkout', { plan: 'pro' })
      window.location.href = resolveTarget(`${checkout.url}?return_to=/billing`)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not start the checkout.')
      setBusy(false)
    }
  }

  if (!plan) {
    return error ? <Alert tone="error">{error}</Alert> : <Spinner label="Loading billing" />
  }

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-white">Billing</h1>
        <p className="mt-1.5 text-sm text-muted">Your plan and every payment you have made.</p>
      </header>

      {error ? <Alert tone="error">{error}</Alert> : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-wide text-muted">Current plan</p>
              <p className="mt-1 text-2xl font-semibold capitalize text-white">{plan.current_plan}</p>
            </div>
            <span className="chip border-brand/40 bg-brand/10 text-brand-soft">
              {formatMoney(plan.price_cents, plan.currency)} / month
            </span>
          </div>

          <ul className="mt-5 flex flex-col gap-2 text-sm text-muted">
            {plan.features.map((feature) => (
              <li key={feature} className="flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" />
                {feature}
              </li>
            ))}
          </ul>

          {plan.current_plan === 'free' ? (
            <Button className="mt-6 w-full" onClick={startCheckout} disabled={busy}>
              {busy ? 'Redirecting…' : 'Upgrade to Pro'}
            </Button>
          ) : (
            <p className="mt-6 text-sm text-positive">You are on the Pro plan. Thanks for supporting the project.</p>
          )}
        </Card>

        <Card className="overflow-x-auto p-0">
          <div className="border-b border-line px-5 py-4">
            <h2 className="text-sm font-semibold text-white">Payment history</h2>
          </div>
          {payments.length === 0 ? (
            <p className="px-5 py-8 text-center text-sm text-muted">No payments recorded yet.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
                  <th className="px-5 py-3 font-medium">Date</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 text-right font-medium">Amount</th>
                </tr>
              </thead>
              <tbody>
                {payments.map((payment) => (
                  <tr key={payment.id} className="border-b border-line/60 last:border-0">
                    <td className="px-5 py-3.5 text-slate-300">{formatDateTime(payment.created_at)}</td>
                    <td className="px-5 py-3.5">
                      <span
                        className={`chip ${
                          payment.status === 'paid'
                            ? 'border-positive/40 bg-positive/10 text-positive'
                            : 'border-caution/40 bg-caution/10 text-caution'
                        }`}
                      >
                        {payment.status}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-right font-medium text-white">
                      {formatMoney(payment.amount_cents, payment.currency)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </div>
  )
}
