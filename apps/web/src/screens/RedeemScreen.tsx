import React from 'react'
import { previewInvite, redeemInvite } from '../api/invites'
import type { User } from '../types'

export function RedeemScreen({ code, onRedeemed }: { code: string; onRedeemed: (token: string, user: User) => Promise<void> }) {
  const [state, setState] = React.useState<'checking' | 'ok' | 'invalid'>('checking')
  const [role, setRole] = React.useState('member')
  const [username, setUsername] = React.useState('')
  const [password, setPassword] = React.useState('')
  const [confirm, setConfirm] = React.useState('')
  const [profileName, setProfileName] = React.useState('Default')
  const [error, setError] = React.useState('')

  React.useEffect(() => {
    previewInvite(code).then(r => { setRole(r.role); setState('ok') }).catch(() => setState('invalid'))
  }, [code])

  async function submit(event: React.FormEvent) {
    event.preventDefault(); setError('')
    if (password !== confirm) return setError('Passwords do not match')
    try {
      const res = await redeemInvite(code, { username, password, profile_name: profileName })
      await onRedeemed(res.token, res.user)
    } catch (err) { setError(String(err)) }
  }

  if (state === 'checking') return <div className="login-screen"><div className="login-card"><div className="brand-mark">H</div><p className="muted">Checking invite…</p></div></div>
  if (state === 'invalid') return <div className="login-screen"><div className="login-card"><div className="brand-mark">H</div><h1>Invite invalid</h1><p className="muted">This invite link is invalid, already used, or expired. Ask your admin for a new one.</p><a className="primary-button" href="/" style={{ textAlign: 'center' }}>Go to login</a></div></div>

  return <div className="login-screen"><form className="login-card wide" onSubmit={submit}>
    <div className="brand-mark">H</div>
    <p className="eyebrow">Join the team{role === 'admin' ? ' · admin' : ''}</p>
    <h1>Create your account</h1>
    <p className="muted">You were invited to Hive OS. Pick a username, password, and your first Hermes profile name.</p>
    <label>Username<input value={username} onChange={e => setUsername(e.target.value)} autoFocus /></label>
    <label>Password<input type="password" value={password} onChange={e => setPassword(e.target.value)} /></label>
    <label>Confirm password<input type="password" value={confirm} onChange={e => setConfirm(e.target.value)} /></label>
    <label>First Hermes profile name<input value={profileName} onChange={e => setProfileName(e.target.value)} /></label>
    {error && <p className="error-text">{error}</p>}
    <button className="primary-button" type="submit" disabled={!username || password.length < 8}>Create account &amp; sign in</button>
  </form></div>
}
