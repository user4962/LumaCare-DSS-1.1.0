export const formatDateTime = (iso: string) => new Intl.DateTimeFormat('en-GB', {
  day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false,
}).format(new Date(iso))

export const formatDate = (iso: string) => new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(iso))

export const formatRelative = (iso: string) => {
  const difference = Date.now() - new Date(iso).getTime()
  const minutes = Math.round(difference / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  return `${Math.round(hours / 24)} d ago`
}

export const formatSeconds = (value: number) => Number.isInteger(value) ? `${value} s` : `${value.toFixed(3)} s`
