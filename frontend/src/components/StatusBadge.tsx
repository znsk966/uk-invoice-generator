import type { InvoiceStatus } from '../api/types'

const STYLES: Record<InvoiceStatus, string> = {
  draft: 'bg-gray-100 text-gray-700',
  issued: 'bg-green-100 text-green-800',
  void: 'bg-amber-100 text-amber-800',
}

export function StatusBadge({ status }: { status: InvoiceStatus }) {
  return (
    <span
      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium capitalize ${STYLES[status]}`}
    >
      {status}
    </span>
  )
}
