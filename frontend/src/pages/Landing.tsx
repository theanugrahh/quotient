import { Link } from 'react-router-dom'

const features = [
  {
    title: 'Quotes that become invoices',
    body: 'Draft a quote, send it with a share link, and mark it paid when the money lands. One record follows the whole path.',
  },
  {
    title: 'Totals you can trust',
    body: 'Line items are priced in cents and totals are recalculated on the server, so a tampered request can never change what a client owes.',
  },
  {
    title: 'A link your client can open',
    body: 'Every sent invoice gets a signed, expiring link. Clients see the breakdown and can pay without creating an account.',
  },
  {
    title: 'Roles that mean something',
    body: 'Administrators manage the whole workspace, everyone else only ever sees their own clients and invoices.',
  },
  {
    title: 'Uploads with limits',
    body: 'Logos and attachments are checked by content type and size before they are stored, and served back through an authorised route.',
  },
  {
    title: 'Payments with signed webhooks',
    body: 'Checkout sessions are reconciled through a signature-verified webhook, and repeated events never double count.',
  },
]

const steps = [
  { step: '01', title: 'Add your client', body: 'A name, an email and a company is all it takes.' },
  { step: '02', title: 'Price the work', body: 'Add line items, set tax and discount, and send it.' },
  { step: '03', title: 'Get paid', body: 'Share the link, collect payment, and watch the dashboard update.' },
]

export function Landing() {
  return (
    <div className="flex flex-col gap-16">
      <section className="pt-6 sm:pt-12">
        <span className="chip border-brand/40 bg-brand/10 text-brand-soft">Quotes · Invoices · Payments</span>
        <h1 className="mt-5 max-w-3xl text-4xl font-semibold leading-tight tracking-tight text-white sm:text-5xl">
          Stop chasing invoices. Send a link, get paid.
        </h1>
        <p className="mt-5 max-w-xl text-base leading-relaxed text-muted">
          Quotient is a small workspace for independent studios and freelancers. Quote the work, share a single
          link with the client, and keep every payment attached to the invoice it belongs to.
        </p>
        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <Link to="/register" className="btn-primary">
            Create your workspace
          </Link>
          <Link to="/login" className="btn-ghost">
            Sign in
          </Link>
        </div>

        <dl className="mt-12 grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[
            ['Invoice totals', 'Server calculated'],
            ['Share links', 'Signed and expiring'],
            ['Webhooks', 'Idempotent'],
            ['Access', 'Role enforced'],
          ].map(([label, value]) => (
            <div key={label} className="surface p-4">
              <dt className="text-xs uppercase tracking-wide text-muted">{label}</dt>
              <dd className="mt-1.5 text-sm font-semibold text-white">{value}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section>
        <h2 className="text-2xl font-semibold tracking-tight text-white">Everything a small studio needs</h2>
        <p className="mt-2 max-w-2xl text-sm text-muted">
          Deliberately small, and deliberately careful with the parts that usually go wrong.
        </p>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => (
            <article key={feature.title} className="surface p-5">
              <h3 className="text-sm font-semibold text-white">{feature.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted">{feature.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-semibold tracking-tight text-white">How it works</h2>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {steps.map((item) => (
            <div key={item.step} className="surface p-5">
              <span className="text-xs font-semibold tracking-widest text-brand">{item.step}</span>
              <h3 className="mt-2 text-base font-semibold text-white">{item.title}</h3>
              <p className="mt-1.5 text-sm text-muted">{item.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="surface flex flex-col items-start justify-between gap-6 p-8 sm:flex-row sm:items-center">
        <div>
          <h2 className="text-xl font-semibold text-white">Ready when you are</h2>
          <p className="mt-1.5 max-w-md text-sm text-muted">
            Set up a workspace in under a minute and send your first invoice today.
          </p>
        </div>
        <Link to="/register" className="btn-primary">
          Get started
        </Link>
      </section>
    </div>
  )
}
