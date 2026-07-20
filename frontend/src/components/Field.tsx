interface FieldProps {
  label: string
  value: string
  onChange: (value: string) => void
  required?: boolean
  type?: 'text' | 'date'
  placeholder?: string
  invalid?: boolean
}

/**
 * A labelled text input. Note `type` is only ever `text` or `date` — money and
 * quantity inputs use `type="text" inputMode="decimal"` (see `LineInputs`),
 * never `type="number"`, whose value is float-shaped.
 */
export function Field({
  label,
  value,
  onChange,
  required = false,
  type = 'text',
  placeholder,
  invalid = false,
}: FieldProps) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-gray-700">
        {label}
        {required ? <span className="text-red-600"> *</span> : null}
      </span>
      <input
        type={type}
        value={value}
        required={required}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className={`w-full rounded-md border px-3 py-2 text-sm focus:border-gray-900 focus:outline-none ${
          invalid ? 'border-red-400 bg-red-50' : 'border-gray-300'
        }`}
      />
    </label>
  )
}
