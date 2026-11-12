import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { api, ApiError } from '../api/client'
import type { Client, Paged } from '../api/types'
import { Alert, Button, Card, EmptyState, Field, Input, Spinner, Textarea } from '../components/ui'
import { formatDate } from '../lib/format'

export function Clients() {
  const [page, setPage] = useState<Paged<Client> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [company, setCompany] = useState('')
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    try {
      setPage(await api.get<Paged<Client>>('/clients'))
    } catch {
      setError('Could not load your clients.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await api.post('/clients', { name, email: email || null, company, notes })
      setName('')
      setEmail('')
      setCompany('')
      setNotes('')
      await load()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not save the client.')
    } finally {
      setSaving(false)
    }
  }

  async function archive(clientId: string) {
    try {
      await api.delete(`/clients/${clientId}`)
      await load()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not archive the client.')
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-white">Clients</h1>
        <p className="mt-1.5 text-sm text-muted">Everyone you invoice, in one place.</p>
      </header>

      {error ? <Alert tone="error">{error}</Alert> : null}

      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <section className="flex flex-col gap-4">
          {loading ? (
            <Spinner label="Loading clients" />
          ) : page && page.items.length > 0 ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {page.items.map((client) => (
                <Card key={client.id} className="flex flex-col gap-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h2 className="text-sm font-semibold text-white">{client.name}</h2>
                      {client.company ? <p className="text-xs text-muted">{client.company}</p> : null}
                    </div>
                    <Button variant="quiet" onClick={() => archive(client.id)}>
                      Archive
                    </Button>
                  </div>
                  {client.email ? <p className="text-xs text-slate-300">{client.email}</p> : null}
                  {client.notes ? <p className="text-xs leading-relaxed text-muted">{client.notes}</p> : null}
                  <p className="text-xs text-muted">Added {formatDate(client.created_at)}</p>
                </Card>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No clients yet"
              body="Add the people and companies you work with so you can start invoicing them."
            />
          )}
        </section>

        <Card className="h-fit">
          <h2 className="text-sm font-semibold text-white">Add a client</h2>
          <form className="mt-4 flex flex-col gap-3" onSubmit={handleSubmit} noValidate>
            <Field label="Name" htmlFor="client-name">
              <Input
                id="client-name"
                required
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Jordan Blake"
              />
            </Field>
            <Field label="Email" htmlFor="client-email">
              <Input
                id="client-email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="jordan@company.com"
              />
            </Field>
            <Field label="Company" htmlFor="client-company">
              <Input
                id="client-company"
                value={company}
                onChange={(event) => setCompany(event.target.value)}
                placeholder="Northwind Ltd"
              />
            </Field>
            <Field label="Notes" htmlFor="client-notes">
              <Textarea
                id="client-notes"
                rows={3}
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                placeholder="Net 30. Prefers email invoices."
              />
            </Field>
            <Button type="submit" disabled={saving}>
              {saving ? 'Saving…' : 'Add client'}
            </Button>
          </form>
        </Card>
      </div>
    </div>
  )
}
