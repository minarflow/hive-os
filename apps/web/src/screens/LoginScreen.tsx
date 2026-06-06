import React from 'react'
import { login } from '../api/auth'
import type { User } from '../types'

export function LoginScreen({ onLogin }: { onLogin: (token: string, user: User) => Promise<void> }) {
  const [username, setUsername] = React.useState('')
  const [password, setPassword] = React.useState('')
  const [error, setError] = React.useState('')
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setError('')
    try { const result = await login(username, password); await onLogin(result.token, result.user) } catch (err) { setError(String(err)) }
  }
  return <div className="login-screen"><form className="login-card" onSubmit={submit}><div className="brand-mark">H</div><p className="eyebrow">Hive OS Team Mode</p><h1>Sign in</h1><p className="muted">Use your Hive OS username and password. Your Hermes profiles stay separate from other users.</p><label>Username<input value={username} onChange={e => setUsername(e.target.value)} /></label><label>Password<input type="password" value={password} onChange={e => setPassword(e.target.value)} /></label>{error && <p className="error-text">{error}</p>}<button className="primary-button" type="submit">Continue</button></form></div>
}
