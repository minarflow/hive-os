import React from 'react'
import { api } from '../api/client'
import { createInvite, listInvites, revokeInvite, type Invite } from '../api/invites'
import type { User } from '../types'

type TeamUser = { id: number; username: string; os_user: string; role: string; created_at: string }

export function UsersScreen({ token, user, onRefresh }: { token: string; user: User; onRefresh: () => Promise<void> }) {
  const [users, setUsers] = React.useState<TeamUser[]>([])
  const [invites, setInvites] = React.useState<Invite[]>([])
  const [role, setRole] = React.useState<'member' | 'admin'>('member')
  const [days, setDays] = React.useState(7)
  const [link, setLink] = React.useState('')
  const [copied, setCopied] = React.useState(false)
  const [error, setError] = React.useState('')

  const refresh = React.useCallback(async () => {
    if (user.role !== 'environment_admin') return
    setUsers((await api<{ users: TeamUser[] }>('/api/users', token)).users)
    setInvites((await listInvites(token)).invites)
  }, [token, user.role])

  React.useEffect(() => { void refresh().catch(err => setError(String(err))) }, [refresh])

  async function generate() {
    setError(''); setCopied(false)
    try {
      const r = await createInvite(token, role, days * 24)
      setLink(`${window.location.origin}/?invite=${r.code}`)
      await refresh()
    } catch (err) { setError(String(err)) }
  }
  async function copy() {
    try { await navigator.clipboard.writeText(link); setCopied(true); window.setTimeout(() => setCopied(false), 1500) } catch { /* */ }
  }
  async function revoke(code: string) {
    try { await revokeInvite(token, code); await refresh() } catch (err) { setError(String(err)) }
  }

  if (user.role !== 'environment_admin') return <section className="placeholder-view"><div className="assistant-bubble compact"><h1>Team Users</h1><p>Environment admin access required.</p></div></section>

  return <section className="users-view">
    <div className="panel"><div className="panel-head"><h3>Team users</h3><span>{users.length}</span></div>{users.map(u => <p className="member-row" key={u.id}><strong>{u.username}</strong><span>{u.role}</span></p>)}</div>

    <div className="panel">
      <div className="panel-head"><h3>Invite a teammate</h3><span>self-register link</span></div>
      <p className="muted">Generate a link; they pick their own username, password &amp; Hermes profile. Single-use.</p>
      <div className="settings-rows" style={{ maxWidth: 'none' }}>
        <span className="srow-label">Role</span>
        <select className="ui-select" value={role} onChange={e => setRole(e.target.value as 'member' | 'admin')}><option value="member">Member</option><option value="admin">Admin</option></select>
        <span className="srow-label">Expires in</span>
        <div className="seg sm">{[1, 7, 30].map(d => <button type="button" key={d} className={days === d ? 'active' : ''} onClick={() => setDays(d)}>{d}d</button>)}</div>
      </div>
      <button className="primary-button" style={{ marginTop: 14 }} onClick={() => void generate()}>Generate invite link</button>
      {link && <div className="invite-link"><code>{link}</code><button className={`ghost-button ${copied ? 'copied' : ''}`} onClick={() => void copy()}>{copied ? 'Copied' : 'Copy'}</button></div>}

      <div className="divider" />
      <p className="eyebrow">Invites</p>
      {invites.length === 0 ? <p className="muted">No invites yet.</p> : invites.map(i => <div className="member-row" key={i.code}>
        <div><strong>{i.role}</strong><small className="muted"> · {i.used_at ? `used by ${i.used_by}` : i.expires_at ? `expires ${new Date(i.expires_at).toLocaleDateString()}` : 'no expiry'}</small></div>
        {!i.used_at && <button className="ghost-button" onClick={() => void revoke(i.code)}>Revoke</button>}
      </div>)}
      {error && <p className="error-text">{error}</p>}
    </div>
  </section>
}
