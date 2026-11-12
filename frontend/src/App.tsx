import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Spinner } from './components/ui'
import { useAuth } from './context/AuthContext'
import { Admin } from './pages/Admin'
import { Billing } from './pages/Billing'
import { Clients } from './pages/Clients'
import { Dashboard } from './pages/Dashboard'
import { InvoiceDetail } from './pages/InvoiceDetail'
import { Invoices } from './pages/Invoices'
import { Landing } from './pages/Landing'
import { Login } from './pages/Login'
import { NewInvoice } from './pages/NewInvoice'
import { PublicInvoice } from './pages/PublicInvoice'
import { Register } from './pages/Register'

function Protected({ children, adminOnly = false }: { children: React.ReactNode; adminOnly?: boolean }) {
  const { user, ready } = useAuth()

  if (!ready) {
    return <Spinner label="Checking your session" />
  }
  if (!user) {
    return <Navigate to="/login" replace />
  }
  if (adminOnly && user.role !== 'admin') {
    return <Navigate to="/dashboard" replace />
  }
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/invoice/:token" element={<PublicInvoice />} />
      <Route element={<Layout />}>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route
          path="/dashboard"
          element={
            <Protected>
              <Dashboard />
            </Protected>
          }
        />
        <Route
          path="/clients"
          element={
            <Protected>
              <Clients />
            </Protected>
          }
        />
        <Route
          path="/invoices"
          element={
            <Protected>
              <Invoices />
            </Protected>
          }
        />
        <Route
          path="/invoices/new"
          element={
            <Protected>
              <NewInvoice />
            </Protected>
          }
        />
        <Route
          path="/invoices/:id"
          element={
            <Protected>
              <InvoiceDetail />
            </Protected>
          }
        />
        <Route
          path="/billing"
          element={
            <Protected>
              <Billing />
            </Protected>
          }
        />
        <Route
          path="/admin"
          element={
            <Protected adminOnly>
              <Admin />
            </Protected>
          }
        />
        <Route path="*" element={<Landing />} />
      </Route>
    </Routes>
  )
}
