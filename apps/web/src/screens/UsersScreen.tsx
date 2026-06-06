import React from 'react'
import { api } from '../api/client'
import type { User } from '../types'

type TeamUser = { id: number; username: string; os_user: string; role: string; created_at: string }

export function UsersScreen({ token, user, onRefresh }: { token: string; user: User; onRefresh: () => Promise<void> }) {
  const [users, setUsers] = React.useState<TeamUser[]>([])
  const [username, setUsername] = React.useState('')
  const [password, setPassword] = React.useState('')
  const [profileName, setProfileName] = React.useState('Default')
  const [error, setError] = React.useState('')
  async function refresh() { if (user.role !== 'environment_admin') return; const body = await api<{ users: TeamUser[] }>('/api/users', token); setUsers(body.users) }
  React.useEffect(() => { void refresh().catch(err => setError(String(err))) }, [token])
  async function create(event: React.FormEvent) { event.preventDefault(); setError(''); try { await api('/api/users', token, { method: 'POST', body: JSON.stringify({ username, password, role: 'member', profile_name: profileName, profile_slug: 'default' }) }); setUsername(''); setPassword(''); setProfileName('Default'); await refresh(); await onRefresh() } catch (err) { setError(String(err)) } }
  if (user.role !== 'environment_admin') return <section className="placeholder-view"><div className="assistant-bubble compact"><h1>Team Users</h1><p>Environment admin access required.</p></div></section>
  return <section className="users-view"><div className="panel"><div className="panel-head"><h3>Team users</h3><span>{users.length}</span></div>{users.map(u => <p className="member-row" key={u.id}><strong>{u.username}</strong><span>{u.role}</span></p>)}</div><div className="panel"><div className="panel-head"><h3>Create user</h3><span>with Hermes setup</span></div><form className="stack-form" onSubmit={create}><label>Username<input value={username} onChange={e => setUsername(e.target.value)} /></label><label>Password<input type="password" value={password} onChange={e => setPassword(e.target.value)} /></label><label>Default Hermes profile<input value={profileName} onChange={e => setProfileName(e.target.value)} /></label><button className="primary-button" disabled={!username || password.length < 8}>Create user</button></form>{error && <p className="error-text">{error}</p>}</div></section>
}
