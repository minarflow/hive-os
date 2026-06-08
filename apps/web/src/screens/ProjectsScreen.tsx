import React from 'react'
import { createProject, inviteMember, listMembers, listInvitable, removeMember, setProjectVisibility, deleteProject, type Member } from '../api/projects'
import { Dropdown } from '../components/ui/Dropdown'
import type { Project } from '../types'

export function ProjectsScreen({ token, projects, onActiveProject, onRefresh }: { token: string; projects: Project[]; onActiveProject: (p: Project) => void; onRefresh: () => Promise<void> }) {
  const [slug, setSlug] = React.useState('')
  const [slugEdited, setSlugEdited] = React.useState(false)
  const [name, setName] = React.useState('')
  const [visibility, setVisibility] = React.useState<'private' | 'shared'>('private')
  const [selected, setSelected] = React.useState<Project | null>(projects[0] || null)
  const [members, setMembers] = React.useState<Member[]>([])
  const [invitable, setInvitable] = React.useState<string[]>([])
  const [error, setError] = React.useState('')
  const msg = (e: unknown) => (e instanceof Error ? e.message : String(e))
  const slugify = (s: string) => s.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
  const isOwner = selected?.role === 'owner'
  React.useEffect(() => {
    if (!selected) { setMembers([]); setInvitable([]); return }
    void listMembers(token, selected.slug).then(b => setMembers(b.members)).catch(() => setMembers([]))
    if (selected.role === 'owner') void listInvitable(token, selected.slug).then(b => setInvitable(b.users)).catch(() => setInvitable([]))
    else setInvitable([])
  }, [selected?.slug, selected?.role, token])
  async function create(event: React.FormEvent) {
    event.preventDefault(); setError('')
    const finalSlug = slug || slugify(name)
    try { const p = await createProject(token, { slug: finalSlug, name: name || finalSlug, visibility }); setSlug(''); setName(''); setSlugEdited(false); setSelected(p); onActiveProject(p); await onRefresh() } catch (err) { setError(msg(err)) }
  }
  async function doInvite(username: string) {
    if (!selected || !username) return; setError('')
    try { await inviteMember(token, selected.slug, username); const b = await listMembers(token, selected.slug); setMembers(b.members); const inv = await listInvitable(token, selected.slug); setInvitable(inv.users); await onRefresh() } catch (err) { setError(msg(err)) }
  }
  async function doRemove(username: string) {
    if (!selected) return; setError('')
    try { await removeMember(token, selected.slug, username); const b = await listMembers(token, selected.slug); setMembers(b.members); const inv = await listInvitable(token, selected.slug).catch(() => ({ users: [] as string[] })); setInvitable(inv.users); await onRefresh() } catch (err) { setError(msg(err)) }
  }
  async function changeVisibility(v: 'private' | 'shared') {
    if (!selected || selected.visibility === v) return
    const others = members.filter(m => m.role !== 'owner')
    if (v === 'private' && others.length && !window.confirm(`Switch "${selected.name}" to Private? ${others.length} member(s) will lose access.`)) return
    setError('')
    try {
      const p = await setProjectVisibility(token, selected.slug, v); setSelected(p); onActiveProject(p)
      const b = await listMembers(token, selected.slug); setMembers(b.members)
      const inv = await listInvitable(token, selected.slug).catch(() => ({ users: [] as string[] })); setInvitable(inv.users)
      await onRefresh()
    } catch (err) { setError(msg(err)) }
  }
  async function removeProject() { if (!selected) return; if (!window.confirm(`Delete project "${selected.name}"? Its files, chats and tasks will be removed. This cannot be undone.`)) return; setError(''); try { await deleteProject(token, selected.slug); setSelected(null); await onRefresh() } catch (err) { setError(msg(err)) } }
  const ownerName = members.find(m => m.role === 'owner')?.username
  const shareRows = [
    ...members.filter(m => m.role !== 'owner').map(m => ({ username: m.username, on: true })),
    ...invitable.map(u => ({ username: u, on: false })),
  ].sort((a, b) => a.username.localeCompare(b.username))
  return <section className="projects-view"><div className="panel project-list-panel"><div className="panel-head"><h3>Projects</h3><span>{projects.length}</span></div>{projects.map(project => <button className={`project-card ${selected?.slug === project.slug ? 'active' : ''}`} key={project.slug} onClick={() => { setSelected(project); onActiveProject(project) }}><strong>{project.name}</strong><small>{project.slug}</small><span>{project.visibility} · {project.role}</span></button>)}</div><div className="panel project-actions-panel"><div className="panel-head"><h3>Create project</h3><span>team mode</span></div><form className="stack-form" onSubmit={create}><label>Name<input value={name} onChange={e => { setName(e.target.value); if (!slugEdited) setSlug(slugify(e.target.value)) }} placeholder="My Project" /></label><label>Slug <span className="muted">(lowercase, auto from name)</span><input value={slug} onChange={e => { setSlugEdited(true); setSlug(slugify(e.target.value)) }} placeholder="my-project" /></label><label>Visibility<Dropdown value={visibility} onChange={v => setVisibility(v as 'private' | 'shared')} options={[{ value: 'private', label: 'Private' }, { value: 'shared', label: 'Shared' }]} /></label><button className="primary-button" disabled={!(slug || slugify(name))}>Create</button></form><div className="divider" /><div className="panel-head"><h3>Sharing</h3><span>{selected?.slug || 'none'}</span></div>{!selected ? <p className="muted">Select a project.</p> : !isOwner ? <p className="muted">{selected.visibility} · you are a {selected.role}.</p> : <><div className="seg sm">{(['private', 'shared'] as const).map(v => <button key={v} className={selected.visibility === v ? 'active' : ''} onClick={() => void changeVisibility(v)}>{v === 'private' ? 'Private' : 'Shared'}</button>)}</div>{ownerName && <p className="member-row"><strong>{ownerName}</strong><span>owner</span></p>}{selected.visibility === 'private' ? <p className="muted" style={{ marginTop: 8 }}>🔒 Only you. Switch to <strong>Shared</strong> to give specific people access.</p> : <div className="member-toggles">{shareRows.length ? shareRows.map(r => <label className="member-toggle" key={r.username}><input type="checkbox" checked={r.on} onChange={() => void (r.on ? doRemove(r.username) : doInvite(r.username))} /><span>{r.username}</span></label>) : <p className="muted" style={{ marginTop: 8 }}>No other registered users yet.</p>}</div>}</>}{selected?.role === 'owner' && <><div className="divider" /><div className="danger-zone"><div><strong>Delete project</strong><small className="muted"> Removes files, chats &amp; tasks. Cannot be undone.</small></div><button className="ghost-button danger" onClick={() => void removeProject()}>Delete “{selected.name}”</button></div></>}{error && <p className="error-text">{error}</p>}</div></section>
}
