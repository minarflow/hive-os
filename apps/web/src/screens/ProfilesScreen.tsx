import React from 'react'
import { createProfile, deleteProfile, updateProfile } from '../api/profiles'
import type { Profile } from '../types'

export function ProfilesScreen({ token, profiles, onActiveProfile, onRefresh }: { token: string; profiles: Profile[]; onActiveProfile: (p: Profile) => void; onRefresh: () => Promise<void> }) {
  const [slug, setSlug] = React.useState('')
  const [name, setName] = React.useState('')
  const [model, setModel] = React.useState('')
  const [error, setError] = React.useState('')
  async function create(event: React.FormEvent) { event.preventDefault(); setError(''); try { const p = await createProfile(token, { slug, name: name || slug, default_model: model || undefined }); setSlug(''); setName(''); setModel(''); onActiveProfile(p); await onRefresh() } catch (err) { setError(String(err)) } }
  async function makeDefault(profile: Profile) { const p = await updateProfile(token, profile.id, { is_default: true }); onActiveProfile(p); await onRefresh() }
  async function remove(profile: Profile) { try { await deleteProfile(token, profile.id); await onRefresh() } catch (err) { setError(String(err)) } }
  return <section className="profiles-view"><div className="panel"><div className="panel-head"><h3>Hermes profiles</h3><span>{profiles.length}</span></div><p className="muted">Each profile gets a separate app-managed HERMES_HOME, so users can keep credentials, sessions, and model defaults separate.</p><div className="runner-grid">{profiles.map(profile => <article className={`runner-card ${profile.is_default ? 'ready' : 'detected'}`} key={profile.id}><div className="runner-card-head"><strong>{profile.name}</strong><span>{profile.is_default ? 'Default' : 'Profile'}</span></div><small>{profile.slug}</small><p>{profile.default_model || 'default Hermes model'}</p><code>{profile.hermes_home || 'managed by Hive OS'}</code><div className="button-row"><button onClick={() => void makeDefault(profile)} disabled={profile.is_default}>Set default</button><button onClick={() => void remove(profile)} disabled={profile.is_default || profiles.length <= 1}>Delete</button></div></article>)}</div></div><div className="panel"><div className="panel-head"><h3>Create agent/Hermes profile</h3><span>per user</span></div><form className="stack-form" onSubmit={create}><label>Slug<input value={slug} onChange={e => setSlug(e.target.value)} placeholder="minarflow" /></label><label>Name<input value={name} onChange={e => setName(e.target.value)} placeholder="Minarflow Agent" /></label><label>Default model<input value={model} onChange={e => setModel(e.target.value)} placeholder="optional" /></label><button className="primary-button" disabled={!slug}>Create profile</button></form>{error && <p className="error-text">{error}</p>}</div></section>
}
