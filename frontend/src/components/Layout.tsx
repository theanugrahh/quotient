import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { initials } from '../lib/format'
import { Button } from './ui'

const navItems = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/clients', label: 'Clients' },
  { to: '/invoices', label: 'Invoices' },
  { to: '/billing', label: 'Billing' },
]

export function Layout() {
  const { user, logout } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()

  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname])

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-40 border-b border-line bg-canvas/85 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
          <Link to={user ? '/dashboard' : '/'} className="flex items-center gap-2.5">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand text-sm font-bold text-white">
              Q
            </span>
            <span className="text-lg font-semibold tracking-tight text-white">Quotient</span>
          </Link>

          {user ? (
            <>
              <nav className="hidden items-center gap-1 md:flex">
                {navItems.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) =>
                      `rounded-lg px-3 py-2 text-sm font-medium transition ${
                        isActive ? 'bg-raised text-white' : 'text-muted hover:text-white'
                      }`
                    }
                  >
                    {item.label}
                  </NavLink>
                ))}
                {user.role === 'admin' ? (
                  <NavLink
                    to="/admin"
                    className={({ isActive }) =>
                      `rounded-lg px-3 py-2 text-sm font-medium transition ${
                        isActive ? 'bg-raised text-white' : 'text-muted hover:text-white'
                      }`
                    }
                  >
                    Admin
                  </NavLink>
                ) : null}
              </nav>

              <div className="hidden items-center gap-3 md:flex">
                <span className="grid h-9 w-9 place-items-center rounded-full bg-raised text-xs font-semibold text-brand-soft">
                  {initials(user.name)}
                </span>
                <div className="leading-tight">
                  <p className="text-sm font-medium text-white">{user.name}</p>
                  <p className="text-xs capitalize text-muted">{user.plan} plan</p>
                </div>
                <Button variant="quiet" onClick={handleLogout}>
                  Sign out
                </Button>
              </div>

              <button
                type="button"
                className="grid h-10 w-10 place-items-center rounded-lg border border-line text-slate-200 md:hidden"
                aria-label="Toggle navigation"
                aria-expanded={menuOpen}
                onClick={() => setMenuOpen((open) => !open)}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M3 6h18M3 12h18M3 18h18" strokeLinecap="round" />
                </svg>
              </button>
            </>
          ) : (
            <div className="flex items-center gap-2">
              <Link to="/login" className="btn-quiet">
                Sign in
              </Link>
              <Link to="/register" className="btn-primary">
                Get started
              </Link>
            </div>
          )}
        </div>

        {user && menuOpen ? (
          <nav className="border-t border-line bg-surface px-4 py-3 md:hidden">
            <div className="flex flex-col gap-1">
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `rounded-lg px-3 py-2.5 text-sm font-medium ${
                      isActive ? 'bg-raised text-white' : 'text-muted'
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
              {user.role === 'admin' ? (
                <NavLink to="/admin" className="rounded-lg px-3 py-2.5 text-sm font-medium text-muted">
                  Admin
                </NavLink>
              ) : null}
              <div className="mt-2 border-t border-line pt-2">
                <p className="px-3 py-1 text-xs text-muted">Signed in as {user.email}</p>
                <Button variant="ghost" className="w-full" onClick={handleLogout}>
                  Sign out
                </Button>
              </div>
            </div>
          </nav>
        ) : null}
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6 sm:py-10">
        <Outlet />
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-6 text-xs text-muted sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p>Quotient — quotes, invoices and payments for independent studios.</p>
          <p>Built with FastAPI, React and PostgreSQL.</p>
        </div>
      </footer>
    </div>
  )
}
