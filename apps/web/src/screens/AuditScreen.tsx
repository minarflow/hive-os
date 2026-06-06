import React from 'react'
import { listAudit, type AuditEntry } from '../api/audit'
import type { User } from '../types'

const fmt = (s: string) => { try { return new Date(s.replace(' ', 'T') + (s.endsWith('Z') ? '' : 'Z')).toLocaleString() } catch { return s } }
const tone = (a: string) => /error|delete|remove|revoke/.test(a) ? 'danger' : /login|redeem|create|invite|provision/.test(a) ? 'accent' : ''

export function AuditScreen({ token, user }: { token: string; user: User }) {
  const [entries, setEntries] = React.useState<AuditEntry[]>([])
  const [q, setQ] = React.useState('')
  const [error, setError] = React.useState('')

  React.useEffect(() => {
    if (user.role !== 'environment_admin') return
    listAudit(token).then(b => setEntries(b.entries)).catch(e => setError(String(e)))
  }, [token, user.role])

  if (user.role !== 'environment_admin') return <section className="placeholder-view"><div className="assistant-bubble compact"><h1>Audit</h1><p>Environment admin access required.</p></div></section>

  const ql = q.trim().toLowerCase()
  const rows = ql ? entries.filter(e => `${e.actor} ${e.action} ${e.target_type} ${e.target_id} ${e.metadata}`.toLowerCase().includes(ql)) : entries

  return <section className="audit-view"><div className="panel">
    <div className="panel-head"><h3>Audit log</h3><span>{entries.length}</span></div>
    <input className="ui-select audit-search" placeholder="Filter by actor, action, target…" value={q} onChange={e => setQ(e.target.value)} />
    <div className="audit-list">
      {rows.length === 0 && <p className="muted">No entries.</p>}
      {rows.map(e => <div className="audit-row" key={e.id}>
        <span className="audit-time">{fmt(e.created_at)}</span>
        <span className="audit-actor">{e.actor || 'system'}</span>
        <span className={`audit-action ${tone(e.action)}`}>{e.action}</span>
        <span className="audit-target" title={`${e.target_type}:${e.target_id}`}>{e.target_type}:{e.target_id}</span>
        {e.metadata && e.metadata !== '{}' ? <span className="audit-meta" title={e.metadata}>{e.metadata}</span> : <span />}
      </div>)}
    </div>
    {error && <p className="error-text">{error}</p>}
  </div></section>
}
