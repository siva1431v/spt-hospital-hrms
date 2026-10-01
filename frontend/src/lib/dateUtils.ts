/**
 * Standard date formatting utility for SPT Hospital HRMS.
 * Enforces the standardized dd/mm/yyyy display format across all dashboard views.
 */
export function formatDate(dateVal: string | Date | null | undefined): string {
  if (!dateVal) return '—'

  try {
    let year: string
    let month: string
    let day: string

    if (typeof dateVal === 'string') {
      const trimmed = dateVal.trim()
      if (!trimmed) return '—'

      // If already in YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS format
      const datePart = trimmed.split('T')[0].split(' ')[0]
      const parts = datePart.split('-')
      if (parts.length === 3 && parts[0].length === 4) {
        year = parts[0]
        month = parts[1].padStart(2, '0')
        day = parts[2].padStart(2, '0')
        return `${day}/${month}/${year}`
      }

      // If in DD/MM/YYYY or DD-MM-YYYY format
      const slashParts = datePart.split('/')
      if (slashParts.length === 3 && slashParts[2].length === 4) {
        return datePart
      }

      const parsed = new Date(trimmed)
      if (isNaN(parsed.getTime())) return trimmed
      day = String(parsed.getDate()).padStart(2, '0')
      month = String(parsed.getMonth() + 1).padStart(2, '0')
      year = String(parsed.getFullYear())
      return `${day}/${month}/${year}`
    }

    if (dateVal instanceof Date) {
      if (isNaN(dateVal.getTime())) return '—'
      day = String(dateVal.getDate()).padStart(2, '0')
      month = String(dateVal.getMonth() + 1).padStart(2, '0')
      year = String(dateVal.getFullYear())
      return `${day}/${month}/${year}`
    }

    return String(dateVal)
  } catch {
    return String(dateVal)
  }
}
