import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { Alert, Button, Field, Input } from '../components/ui'
import { useAuth } from '../context/AuthContext'

export function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await register(name, email, password)
      navigate('/dashboard', { replace: true })
    } catch (caught) {
      if (caught instanceof ApiError) {
        const detail = caught.fields?.map((item) => item.message).join(' ')
        setError(detail ? `${caught.message} ${detail}` : caught.message)
      } else {
        setError('Could not create the account. Please try again.')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-md flex-col gap-6 py-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-white">Create your workspace</h1>
        <p className="mt-1.5 text-sm text-muted">Free while you send your first few invoices.</p>
      </div>

      {error ? <Alert tone="error">{error}</Alert> : null}

      <form className="surface flex flex-col gap-4 p-6" onSubmit={handleSubmit} noValidate>
        <Field label="Your name" htmlFor="name">
          <Input
            id="name"
            autoComplete="name"
            required
            minLength={2}
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Alex Rivera"
          />
        </Field>

        <Field label="Work email" htmlFor="email">
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@studio.com"
          />
        </Field>

        <Field
          label="Password"
          htmlFor="password"
          hint="At least 10 characters with a letter and a number."
        >
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={10}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </Field>

        <Button type="submit" disabled={busy} className="mt-1 w-full">
          {busy ? 'Creating…' : 'Create account'}
        </Button>
      </form>

      <p className="text-center text-sm text-muted">
        Already have an account?{' '}
        <Link to="/login" className="font-medium text-brand-soft hover:text-white">
          Sign in
        </Link>
      </p>
    </div>
  )
}
