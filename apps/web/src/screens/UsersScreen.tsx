import React from 'react'
import { createInvite, listInvites, revokeInvite, type Invite } from '../api/invites'
import { listUsers, updateUser, deleteUser, type TeamUser } from '../api/users'
import { Dropdown } from '../components/ui/Dropdown'
import type { User } from '../types'

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
    setUsers((await listUsers(token)).users)
    setInvites((await listInvites(token)).invites)
  }, [token, user.role])

  React.useEffect(() => { void refresh().catch(err => setError(String(err))) }, [refresh])

  async function generate() {
    setError(''); setCopied(false)
    try {
      const r = await createInvite(token, role, days * 24)
      setLink(r.link || `${window.location.origin}/?invite=${r.code}`)
      await refresh()
    } catch (err) { setError(String(err)) }
  }
  async function copy() {
    try { await navigator.clipboard.writeText(link); setCopied(true); window.setTimeout(() => setCopied(false), 1500) } catch { /* */ }
  }
  async function revoke(code: string) {
    try { await revokeInvite(token, code); await refresh() } catch (err) { setError(String(err)) }
  }
  async function changeRole(u: TeamUser, nextRole: string) {
    if (nextRole === u.role) return
    setError('')
    try { await updateUser(token, u.id, { role: nextRole }); await refresh(); await onRefresh() } catch (err) { setError(String(err)) }
  }
  async function removeUser(u: TeamUser) {
    if (!window.confirm(`Delete user "${u.username}"? Their chats & profiles will be removed.`)) return
    setError('')
    try { await deleteUser(token, u.id); await refresh(); await onRefresh() } catch (err) { setError(String(err)) }
  }

  if (user.role !== 'environment_admin') return <section className="placeholder-view"><div className="assistant-bubble compact"><h1>Team Users</h1><p>Environment admin access required.</p></div></section>

  return <section className="users-view">
    <div className="panel"><div className="panel-head"><h3>Team users</h3><span>{users.length}</span></div>{users.map(u => <div className="member-row" key={u.id}>
      <strong>{u.username}{u.id === user.id && <span className="muted"> (you)</span>}</strong>
      <div className="member-actions">
        <Dropdown value={u.role === 'environment_admin' ? 'environment_admin' : 'member'} disabled={u.id === user.id} onChange={r => void changeRole(u, r)} options={[{ value: 'member', label: 'Member' }, { value: 'environment_admin', label: 'Admin' }]} />
        {u.id !== user.id && <button className="ghost-button danger" onClick={() => void removeUser(u)}>Delete</button>}
      </div>
    </div>)}</div>

    <div className="panel">
      <div className="panel-head"><h3>Invite a teammate</h3><span>self-register link</span></div>
      <p className="muted">Generate a link; they pick their own username, password &amp; Hermes profile. Single-use.</p>
      <div className="settings-rows" style={{ maxWidth: 'none' }}>
        <span className="srow-label">Role</span>
        <Dropdown value={role} onChange={r => setRole(r as 'member' | 'admin')} options={[{ value: 'member', label: 'Member' }, { value: 'admin', label: 'Admin' }]} />
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
