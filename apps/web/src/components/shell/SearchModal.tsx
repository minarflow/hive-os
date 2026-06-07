import React from 'react'
import type { ChatSession, Project } from '../../types'
import { search, type SearchResults } from '../../api/search'

const EMPTY: SearchResults = { projects: [], chats: [], tasks: [], messages: [] }

export function SearchModal(props: {
  token: string
  sessions: ChatSession[]
  projects: Project[]
  onClose: () => void
  onSelectSession: (s: ChatSession) => void
  onOpenTask: (taskId: number) => void
  onSelectProject: (p: Project) => void
  onSelectView: (v: 'chat') => void
}) {
  const [q, setQ] = React.useState('')
  const [res, setRes] = React.useState<SearchResults>(EMPTY)
  const [loading, setLoading] = React.useState(false)

  React.useEffect(() => {
    const term = q.trim()
    if (term.length < 2) { setRes(EMPTY); return }
    setLoading(true)
    const h = window.setTimeout(() => {
      search(props.token, term).then(setRes).catch(() => setRes(EMPTY)).finally(() => setLoading(false))
    }, 200)
    return () => clearTimeout(h)
  }, [q, props.token])

  const openSession = (id: number, taskId: number | null) => {
    if (taskId) { props.onOpenTask(taskId); props.onClose(); return }
    const s = props.sessions.find(x => x.id === id)
    if (s) { props.onSelectSession(s); props.onSelectView('chat') }
    props.onClose()
  }
  const openProject = (slug: string) => { const p = props.projects.find(x => x.slug === slug); if (p) props.onSelectProject(p); props.onClose() }

  const total = res.projects.length + res.chats.length + res.tasks.length + res.messages.length
  return <div className="modal-scrim" onClick={props.onClose}><div className="modal-card search-modal" onClick={e => e.stopPropagation()}>
    <input autoFocus className="ui-select search-input" placeholder="Search chats, tasks, projects, messages…" value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => { if (e.key === 'Escape') props.onClose() }} />
    <div className="search-results">
      {q.trim().length >= 2 && !loading && total === 0 && <p className="muted">No matches.</p>}
      {res.projects.length > 0 && <div className="search-group"><p className="eyebrow">Projects</p>{res.projects.map(p => <button className="search-item" key={'p' + p.slug} onClick={() => openProject(p.slug)}><strong>{p.name}</strong><small>{p.slug}</small></button>)}</div>}
      {res.tasks.length > 0 && <div className="search-group"><p className="eyebrow">Tasks</p>{res.tasks.map(t => <button className="search-item" key={'t' + t.id} onClick={() => { props.onOpenTask(t.id); props.onClose() }}><strong>{t.title}</strong><small>{t.project_slug} · {t.status}</small></button>)}</div>}
      {res.chats.length > 0 && <div className="search-group"><p className="eyebrow">Chats</p>{res.chats.map(c => <button className="search-item" key={'c' + c.id} onClick={() => openSession(c.id, c.task_id)}><strong>{c.title}</strong></button>)}</div>}
      {res.messages.length > 0 && <div className="search-group"><p className="eyebrow">Messages</p>{res.messages.map((m, i) => <button className="search-item" key={'m' + i} onClick={() => openSession(m.session_id, m.task_id)}><strong>{m.session_title}</strong><small>{m.role}: {m.snippet}</small></button>)}</div>}
    </div>
  </div></div>
}
