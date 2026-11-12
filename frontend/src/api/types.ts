export type InvoiceStatus = 'draft' | 'sent' | 'paid' | 'void'
export type UserRole = 'user' | 'admin'
export type UserPlan = 'free' | 'pro'

export interface User {
  id: string
  name: string
  email: string
  role: UserRole
  plan: UserPlan
  is_active: boolean
  created_at: string
}

export interface Session {
  user: User
  csrf_token: string
  expires_at: string
}

export interface Client {
  id: string
  name: string
  email: string | null
  company: string
  notes: string
  archived: boolean
  created_at: string
}

export interface LineItem {
  id: string
  description: string
  quantity: string
  unit_price_cents: number
  amount_cents: number
}

export interface Invoice {
  id: string
  number: string
  status: InvoiceStatus
  currency: string
  client: Client
  items: LineItem[]
  subtotal_cents: number
  discount_cents: number
  tax_cents: number
  total_cents: number
  notes: string
  issue_date: string
  due_date: string | null
  paid_at: string | null
  share_token: string | null
  share_expires_at: string | null
  created_at: string
  updated_at: string
}

export interface InvoiceSummary {
  id: string
  number: string
  status: InvoiceStatus
  currency: string
  client_name: string
  client_company: string
  total_cents: number
  issue_date: string
  due_date: string | null
  created_at: string
}

export interface PageMeta {
  page: number
  page_size: number
  total: number
  pages: number
}

export interface Paged<T> {
  items: T[]
  meta: PageMeta
}

export interface DashboardStats {
  total_invoices: number
  draft_count: number
  sent_count: number
  paid_count: number
  void_count: number
  outstanding_cents: number
  collected_cents: number
  client_count: number
  currency: string
}

export interface ShareLink {
  token: string
  path: string
  expires_at: string | null
}

export interface Attachment {
  id: string
  original_name: string
  content_type: string
  size_bytes: number
  invoice_id: string | null
  created_at: string
  download_path: string
}

export interface Plan {
  current_plan: UserPlan
  price_cents: number
  currency: string
  features: string[]
}

export interface Checkout {
  session_id: string
  url: string
}

export interface Payment {
  id: string
  provider: string
  amount_cents: number
  currency: string
  status: string
  plan: string
  invoice_id: string | null
  created_at: string
}

export interface AdminUser extends User {
  invoice_count: number
}

export interface AdminStats {
  users: number
  active_users: number
  admins: number
  invoices: number
  clients: number
  paid_invoices: number
  gross_collected_cents: number
}

export interface AuditEvent {
  id: string
  actor_id: string | null
  action: string
  entity_type: string
  entity_id: string | null
  ip_address: string | null
  created_at: string
}

export interface PublicInvoice {
  number: string
  status: InvoiceStatus
  currency: string
  studio_name: string
  client_name: string
  client_company: string
  items: LineItem[]
  subtotal_cents: number
  discount_cents: number
  tax_cents: number
  total_cents: number
  notes: string
  issue_date: string
  due_date: string | null
}
