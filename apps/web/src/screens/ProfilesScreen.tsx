import React from 'react'
import { createProfile, deleteProfile, updateProfile } from '../api/profiles'
import type { Profile } from '../types'
import { Dropdown } from '../components/ui/Dropdown'

type RunnerReadiness = Record<string, { displayName: string; installed: boolean; ready: boolean; authHint: string }>

export function ProfilesScreen({ token, profiles, onActiveProfile, onRefresh }: { token: string; profiles: Profile[]; onActiveProfile: (p: Profile) => void; onRefresh: () => Promise<void> }) {
  const [slug, setSlug] = React.useState('')
  const [name, setName] = React.useState('')
  const [model, setModel] = React.useState('')
  const [runner, setRunner] = React.useState('hermes')
  const [readiness, setReadiness] = React.useState<RunnerReadiness>({})
  const [error, setError] = React.useState('')

  React.useEffect(() => {
    if (!token) return
    fetch('/api/runners/detect', { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json()).then(b => setReadiness(b.runnerReadiness || {})).catch(() => setReadiness({}))
  }, [token])

  async function create(event: React.FormEvent) {
    event.preventDefault()
    setError('')
    try {
      const p = await createProfile(token, { slug, name: name || slug, default_model: model || undefined, runner_id: runner })
      setSlug(''); setName(''); setModel(''); setRunner('hermes')
      onActiveProfile(p)
      await onRefresh()
    } catch (err) { setError(String(err)) }
  }
  async function makeDefault(profile: Profile) { const p = await updateProfile(token, profile.id, { is_default: true }); onActiveProfile(p); await onRefresh() }
  async function remove(profile: Profile) { try { await deleteProfile(token, profile.id); await onRefresh() } catch (err) { setError(String(err)) } }
  async function changeRunner(profile: Profile, runner_id: string) {
    try { await updateProfile(token, profile.id, { runner_id }); await onRefresh() } catch (err) { setError(String(err)) }
  }

  const runnerOptions = Object.values(readiness).length
    ? Object.entries(readiness).map(([id, r]) => ({ value: id, label: r.displayName + (r.installed ? '' : ' (not installed)'), badge: r.ready ? 'ready' : undefined }))
    : [{ value: 'hermes', label: 'Hermes' }]

  return <section className="profiles-view"><div className="panel"><div className="panel-head"><h3>Agent profiles</h3><span>{profiles.length}</span></div><p className="muted">Each profile gets its own app-managed agent home, so users keep credentials, sessions, and model defaults separate.</p><div className="runner-grid">{profiles.map(profile => <article className={`runner-card ${profile.is_default ? 'ready' : 'detected'}`} key={profile.id}><div className="runner-card-head"><strong>{profile.name}</strong><span>{profile.is_default ? 'Default' : 'Profile'}</span></div><small>{profile.slug}</small><p>{profile.default_model || 'default model'}</p><code>{profile.hermes_home || 'managed by Hive OS'}</code><label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '.8rem', marginTop: 4 }}><span className="muted">Runner</span><Dropdown value={profile.runner_id || 'hermes'} onChange={v => void changeRunner(profile, v)} options={runnerOptions} minWidth={120} /></label><div className="button-row"><button onClick={() => void makeDefault(profile)} disabled={profile.is_default}>Set default</button><button onClick={() => void remove(profile)} disabled={profile.is_default || profiles.length <= 1}>Delete</button></div></article>)}</div></div><div className="panel"><div className="panel-head"><h3>Create agent profile</h3><span>per user</span></div><form className="stack-form" onSubmit={create}><label>Slug<input value={slug} onChange={e => setSlug(e.target.value)} placeholder="minarflow" /></label><label>Name<input value={name} onChange={e => setName(e.target.value)} placeholder="Minarflow Agent" /></label><label>Runner<Dropdown value={runner} onChange={setRunner} options={runnerOptions} /></label>{readiness[runner] && !readiness[runner].ready && readiness[runner].authHint && <p className="muted" style={{ marginTop: -4, fontSize: '.8rem' }}>{readiness[runner].authHint}</p>}<label>Default model<input value={model} onChange={e => setModel(e.target.value)} placeholder="optional" /></label><button className="primary-button" disabled={!slug}>Create profile</button></form>{error && <p className="error-text">{error}</p>}</div></section>
}
