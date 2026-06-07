import React from 'react'

type HermesStatus = { ready: boolean; binary: string | null; home: string | null; guidance: string }

export function HermesBanner({ token }: { token: string }) {
  const [status, setStatus] = React.useState<HermesStatus | null>(null)
  React.useEffect(() => {
    if (!token) return
    fetch('/api/runners/detect', { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json()).then(b => setStatus(b.hermes ?? null)).catch(() => setStatus(null))
  }, [token])
  if (!status || status.ready) return null
  return <div className="hermes-banner" role="status">⚠ Hermes runner not ready — {status.guidance}</div>
}
