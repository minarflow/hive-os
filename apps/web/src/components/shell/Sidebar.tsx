import type { ComponentType } from 'react'
import type { ChatSession, Profile, Project, User, View } from '../../types'
import { IconNewChat, IconProjects, IconAgents, IconUsers, IconGear, IconClose, IconPencil, IconTrash } from './icons'

type NavItem = { id: View; label: string; icon: ComponentType<{ size?: number }>; action?: 'new-chat' }

const nav: NavItem[] = [
  { id: 'chat', label: 'New Chat', icon: IconNewChat, action: 'new-chat' },
  { id: 'projects', label: 'Projects', icon: IconProjects },
  { id: 'profiles', label: 'Agents', icon: IconAgents },
  { id: 'users', label: 'Team Users', icon: IconUsers }
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
  onSelectView: (view: View) => void
  profiles: Profile[]
  projects: Project[]
  sessions: ChatSession[]
  user: User
}) {
  const shared = props.projects.filter(project => project.visibility === 'shared')
  return <div className="sidebar-inner">
    <div className="sidebar-head"><div className="brand-row"><span className="brand-dot">H</span><strong>Hive OS</strong></div><div className="sidebar-actions"><button className="icon-button mobile-only" onClick={props.onClose} aria-label="Close menu"><IconClose size={18} /></button></div></div>
    <section className="nav-group">{nav.filter(item => item.id !== 'users' || props.user.role === 'environment_admin').map(item => {
      const Icon = item.icon
      const onClick = () => {
        if (item.action === 'new-chat') props.onNewChat()
        else props.onSelectView(item.id)
        props.onClose()
      }
      return <button className={`nav-item ${props.currentView === item.id && !item.action ? 'active' : ''}`} key={item.id} onClick={onClick}><span className="nav-icon"><Icon /></span><strong>{item.label}</strong></button>
    })}</section>
    {shared.length > 0 && <section className="nav-group projects-mini"><button className="group-toggle"><span>Shared</span><span>{shared.length}</span></button>{shared.map(project => <button className={`project-row ${props.activeProject?.slug === project.slug ? 'active' : ''}`} key={project.slug} onClick={() => { props.onSelectProject(project); props.onSelectView('chat'); props.onClose() }} title={`${project.slug} · ${project.role}`}><span className="status-dot" /><div><strong>{project.name}</strong></div></button>)}</section>}
    {props.sessions.length > 0 && <section className="nav-group"><button className="group-toggle"><span>Sessions</span><span>{props.sessions.length}</span></button>{props.sessions.slice(0, 20).map(session => <div className={`project-row session-row ${props.activeSession?.id === session.id ? 'active' : ''}`} key={session.id} title={`${session.project_slug || 'no project'} · ${session.profile_slug || 'profile'}`}>
      <button className="row-main" onClick={() => { props.onSelectSession(session); props.onClose() }}><span className="status-dot" /><strong>{session.title}</strong></button>
      <span className="row-actions">
        <button className="row-action" title="Rename" aria-label="Rename session" onClick={e => { e.stopPropagation(); const t = window.prompt('Rename session', session.title); if (t && t.trim()) props.onRenameSession(session.id, t.trim()) }}><IconPencil size={15} /></button>
        <button className="row-action danger" title="Delete" aria-label="Delete session" onClick={e => { e.stopPropagation(); if (window.confirm(`Delete session "${session.title}"?`)) props.onDeleteSession(session.id) }}><IconTrash size={15} /></button>
      </span>
    </div>)}</section>}
    <div className="user-card"><span className="avatar">{props.user.username[0]?.toUpperCase()}</span><div><strong>{props.user.username}</strong><small>{props.activeProfile?.name || props.user.role}</small></div><button className={`icon-button settings-button ${props.currentView === 'settings' ? 'active' : ''}`} title="Settings" aria-label="Settings" onClick={() => { props.onSelectView('settings'); props.onClose() }}><IconGear /></button></div>
  </div>
}
