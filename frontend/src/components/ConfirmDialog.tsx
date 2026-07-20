import type { ReactNode } from 'react'

interface ConfirmDialogProps {
  title: string
  confirmLabel: string
  onConfirm: () => void
  onCancel: () => void
  busy?: boolean
  children?: ReactNode
}

/**
 * Minimal modal. Used for every irreversible-ish action: archiving a client,
 * deleting a draft, issuing, voiding.
 */
export function ConfirmDialog({
  title,
  confirmLabel,
  onConfirm,
  onCancel,
  busy = false,
  children,
}: ConfirmDialogProps) {
  return (
    <div className="fixed inset-0 z-10 flex items-center justify-center bg-gray-900/40 p-4">
      <div role="dialog" aria-label={title} className="w-full max-w-md rounded-lg bg-white p-6 shadow-lg">
        <h2 className="text-lg font-semibold">{title}</h2>
        <div className="mt-3 text-sm text-gray-700">{children}</div>
        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-gray-300 px-3 py-2 text-sm hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className="rounded-md bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
          >
            {busy ? 'Working…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
