import React from 'react'
import { bootstrap } from '../api/auth'
import { Dropdown } from '../components/ui/Dropdown'
import type { User } from '../types'

export function SetupScreen({ onComplete }: { onComplete: (token: string, user: User) => Promise<void> }) {
  const [username, setUsername] = React.useState('kuya')
  const [password, setPassword] = React.useState('')
  const [confirm, setConfirm] = React.useState('')
  const [profileName, setProfileName] = React.useState('Default')
  const [profileSlug, setProfileSlug] = React.useState('default')
  const [runner, setRunner] = React.useState('hermes')
  const [runners, setRunners] = React.useState<{ id: string; displayName: string; installed: boolean }[]>([])
  const [error, setError] = React.useState('')

  React.useEffect(() => {
    fetch('/api/setup/status').then(r => r.json()).then(d => setRunners(d.runners || [])).catch(() => setRunners([]))
  }, [])

  const runnerOptions = runners.length
    ? runners.map(r => ({ value: r.id, label: r.displayName + (r.installed ? '' : ' (not installed)') }))
    : [{ value: 'hermes', label: 'Hermes' }]

  async function submit(event: React.FormEvent) {
    event.preventDefault(); setError('')
    if (password !== confirm) return setError('Passwords do not match')
    try {
      const result = await bootstrap({ username, password, profile_name: profileName, profile_slug: profileSlug, runner_id: runner })
      await onComplete(result.token, result.user)
    } catch (err) { setError(String(err)) }
  }
  return <div className="login-screen"><form className="login-card wide" onSubmit={submit}><div className="brand-mark">H</div><p className="eyebrow">First-run Team Mode</p><h1>Set up Hive OS</h1><p className="muted">Create the first admin. Every user gets their own managed agent profiles.</p><label>Admin username<input value={username} onChange={e => setUsername(e.target.value)} /></label><label>Password<input type="password" value={password} onChange={e => setPassword(e.target.value)} /></label><label>Confirm password<input type="password" value={confirm} onChange={e => setConfirm(e.target.value)} /></label><label>First profile name<input value={profileName} onChange={e => setProfileName(e.target.value)} /></label><label>Profile slug<input value={profileSlug} onChange={e => setProfileSlug(e.target.value)} /></label><label>Runner<Dropdown value={runner} onChange={setRunner} options={runnerOptions} /></label>{error && <p className="error-text">{error}</p>}<button className="primary-button" type="submit">Create team workspace</button></form></div>
}
