import type { ChatSession, Profile, Project, User, View } from '../../types'

const nav: Array<{ id: View; label: string }> = [
  { id: 'chat', label: 'Chat' },
  { id: 'projects', label: 'Projects' },
  { id: 'profiles', label: 'Agents / Hermes Profiles' },
  { id: 'runners', label: 'Runners' },
  { id: 'users', label: 'Team Users' },
  { id: 'settings', label: 'Settings' }
]

export function Sidebar(props: {
  activeProfile: Profile | null
  activeProject: Project | null
  activeSession: ChatSession | null
  currentView: View
  onClose: () => void
  onLogout: () => void
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
    <div className="sidebar-head"><div className="brand-row"><span className="brand-dot">H</span><strong>Hive OS</strong></div><div className="sidebar-actions"><button className="icon-button mobile-only" onClick={props.onClose}>×</button></div></div>
    <div className="search-pill">Team Mode · Hermes per profile</div>
    <section className="nav-group"><button className="group-toggle"><span>Workspace</span></button>{nav.filter(item => item.id !== 'users' || props.user.role === 'environment_admin').map(item => <button className={`nav-item ${props.currentView === item.id ? 'active' : ''}`} key={item.id} onClick={() => { props.onSelectView(item.id); props.onClose() }}><span className="nav-icon">⌁</span><strong>{item.label}</strong></button>)}</section>
    <section className="nav-group projects-mini"><button className="group-toggle"><span>Linc-Projects</span><span>{shared.length}</span></button>{shared.length === 0 ? <span className="empty-mini">No shared projects yet</span> : shared.map(project => <button className={`project-row ${props.activeProject?.slug === project.slug ? 'active' : ''}`} key={project.slug} onClick={() => { props.onSelectProject(project); props.onSelectView('chat'); props.onClose() }}><span className="status-dot" /><div><strong>{project.name}</strong><small>{project.slug} · {project.role}</small></div></button>)}</section>
    <section className="nav-group"><button className="group-toggle"><span>Sessions</span><span>{props.sessions.length}</span></button>{props.sessions.slice(0, 12).map(session => <button className={`project-row ${props.activeSession?.id === session.id ? 'active' : ''}`} key={session.id} onClick={() => { props.onSelectSession(session); props.onClose() }}><span className="status-dot" /><div><strong>{session.title}</strong><small>{session.project_slug || 'no project'} · {session.profile_slug || 'profile'}</small></div></button>)}</section>
    <div className="user-card"><span className="avatar">{props.user.username[0]?.toUpperCase()}</span><div><strong>{props.user.username}</strong><small>{props.activeProfile?.name || props.user.role}</small></div><button className="logout-button" onClick={props.onLogout}>Logout</button></div>
  </div>
}
