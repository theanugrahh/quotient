import { describe, expect, it } from 'vitest'
import { formatDate, formatMoney, initials, relativeDays, statusLabels } from '../lib/format'

describe('formatMoney', () => {
  it('renders cents with the currency symbol', () => {
    expect(formatMoney(156_750, 'usd')).toBe('$1,567.50')
    expect(formatMoney(0, 'usd')).toBe('$0.00')
    expect(formatMoney(2_500, 'eur')).toBe('€25.00')
  })

  it('falls back to the currency code for unknown currencies', () => {
    expect(formatMoney(1_000, 'sek')).toBe('10.00 SEK')
  })
})

describe('formatDate', () => {
  it('returns a dash for missing or invalid dates', () => {
    expect(formatDate(null)).toBe('—')
    expect(formatDate('not-a-date')).toBe('—')
  })

  it('formats a valid date', () => {
    expect(formatDate('2026-03-04T10:00:00Z')).toMatch(/2026/)
  })
})

describe('relativeDays', () => {
  it('describes a future date', () => {
    const future = new Date(Date.now() + 3 * 86_400_000).toISOString()
    expect(relativeDays(future)).toBe('in 3 days')
  })

  it('describes a past date', () => {
    const past = new Date(Date.now() - 2 * 86_400_000).toISOString()
    expect(relativeDays(past)).toBe('2 days ago')
  })
})

describe('statusLabels', () => {
  it('covers every invoice status', () => {
    expect(statusLabels).toEqual({ draft: 'Draft', sent: 'Sent', paid: 'Paid', void: 'Void' })
  })
})

describe('initials', () => {
  it('takes the first two words', () => {
    expect(initials('Alex Rivera Santos')).toBe('AR')
    expect(initials('Alex')).toBe('A')
    expect(initials('')).toBe('')
  })
})
