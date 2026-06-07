import React from 'react'
import type { ComponentType } from 'react'
import type { ChatSession, Profile, Project, User, View } from '../../types'
import { IconNewChat, IconProjects, IconClose, IconPencil, IconTrash, IconWiki, IconFile, IconTasks } from './icons'
import { ProjectSwitcher } from './ProjectSwitcher'

type NavItem = { id: View; label: string; icon: ComponentType<{ size?: number }>; action?: 'new-chat' }

// Work-focused nav. Account/management (Agents, Team Users, Settings) live in the
// top-right profile menu.
const nav: NavItem[] = [
  { id: 'chat', label: 'New Chat', icon: IconNewChat, action: 'new-chat' },
  { id: 'projects', label: 'Projects', icon: IconProjects },
  { id: 'wiki', label: 'Wiki', icon: IconWiki },
  { id: 'artifacts', label: 'Files', icon: IconFile },
  { id: 'tasks', label: 'Tasks', icon: IconTasks }
]

export function Sidebar(props: {
  activeProfile: Profile | null
  activeProject: Project | null
  activeSession: ChatSession | null
  currentView: View
  onClose: () => void
  onLogout: () => void
  onNewChat: () => void
  onRenameSession: (id: number, title: string) => void
  onDeleteSession: (id: number) => void
  onSelectProject: (project: Project) => void
  onSelectSession: (session: ChatSession) => void
  onOpenTask: (taskId: number) => void
  onSelectView: (view: View) => void
  profiles: Profile[]
  projects: Project[]
  sessions: ChatSession[]
  seen: Record<number, string>
  user: User
}) {
  return <div className="sidebar-inner">
    <div className="sidebar-head"><div className="brand-row"><span className="brand-dot">H</span><strong>Hive OS</strong></div><div className="sidebar-actions"><button className="icon-button mobile-only" onClick={props.onClose} aria-label="Close menu"><IconClose size={18} /></button></div></div>
    <section className="nav-group">{nav.map(item => {
      const Icon = item.icon
      const onClick = () => {
        if (item.action === 'new-chat') props.onNewChat()
        else props.onSelectView(item.id)
        props.onClose()
      }
      return <button className={`nav-item ${props.currentView === item.id && !item.action ? 'active' : ''}`} key={item.id} onClick={onClick}><span className="nav-icon"><Icon /></span><strong>{item.label}</strong></button>
    })}</section>
    <section className="nav-group sidebar-projects"><p className="eyebrow">Project</p><ProjectSwitcher projects={props.projects} activeProject={props.activeProject} onSelect={p => { props.onSelectProject(p); props.onClose() }} /></section>
    <SessionGroups {...props} />
  </div>
}

type GroupProps = {
  sessions: ChatSession[]; activeSession: ChatSession | null; onClose: () => void
  onSelectSession: (s: ChatSession) => void; onRenameSession: (id: number, t: string) => void
  onDeleteSession: (id: number) => void; onOpenTask: (taskId: number) => void
  seen: Record<number, string>
}

const isUnread = (s: ChatSession, seen: Record<number, string>) => (seen[s.id] ?? '') < (s.updated_at ?? '')

function usePersistedToggle(key: string, fallback: boolean) {
  const [open, setOpen] = React.useState(() => { const v = localStorage.getItem(key); return v == null ? fallback : v === '1' })
  const toggle = () => setOpen(v => { localStorage.setItem(key, v ? '0' : '1'); return !v })
  return [open, toggle] as const
}

function SessionGroups(props: GroupProps) {
  const chats = props.sessions.filter(s => !s.task_id)
  const taskThreads = props.sessions.filter(s => s.task_id)
  const [openChats, toggleChats] = usePersistedToggle('hive.sb.chats', true)
  const [openTasks, toggleTasks] = usePersistedToggle('hive.sb.tasks', false)

  return <>
    {chats.length > 0 && <section className="nav-group">
      <button className="group-toggle" onClick={toggleChats}><span><span className={`chevron ${openChats ? 'open' : ''}`}>▸</span> Chats</span><span>{chats.length}</span></button>
      {openChats && chats.slice(0, 20).map(session => <div className={`project-row session-row ${props.activeSession?.id === session.id ? 'active' : ''}`} key={session.id} title={`${session.project_slug || 'no project'} · ${session.profile_slug || 'profile'}`}>
        <button className="row-main" onClick={() => { props.onSelectSession(session); props.onClose() }}><span className={`status-dot ${session.id !== props.activeSession?.id && isUnread(session, props.seen) ? 'unread' : ''}`} /><strong>{session.title}</strong></button>
        <span className="row-actions">
          <button className="row-action" title="Rename" aria-label="Rename session" onClick={e => { e.stopPropagation(); const t = window.prompt('Rename session', session.title); if (t && t.trim()) props.onRenameSession(session.id, t.trim()) }}><IconPencil size={15} /></button>
          <button className="row-action danger" title="Delete" aria-label="Delete session" onClick={e => { e.stopPropagation(); if (window.confirm(`Delete session "${session.title}"?`)) props.onDeleteSession(session.id) }}><IconTrash size={15} /></button>
        </span>
      </div>)}
    </section>}
    {taskThreads.length > 0 && <section className="nav-group">
      <button className="group-toggle" onClick={toggleTasks}><span><span className={`chevron ${openTasks ? 'open' : ''}`}>▸</span> Tasks</span><span>{taskThreads.length}</span></button>
      {openTasks && taskThreads.slice(0, 30).map(session => <div className="project-row session-row" key={session.id} title="Open task">
        <button className="row-main" onClick={() => { props.onOpenTask(session.task_id as number); props.onClose() }}><span className={`status-dot ${isUnread(session, props.seen) ? 'unread' : ''}`} /><strong>{session.task_title || session.title}</strong></button>
      </div>)}
    </section>}
  </>
}
