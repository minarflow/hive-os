import React from 'react'
import type { ChatSession, Profile, Project, User, View } from '../../types'
import { Sidebar } from './Sidebar'
import { MobileTopbar } from './MobileTopbar'
import { RightRail } from './RightRail'

export function AppShell(props: {
  children: React.ReactNode
  activeProfile: Profile | null
  activeProject: Project | null
  activeSession: ChatSession | null
  currentView: View
  onLogout: () => void
  onSelectProject: (project: Project) => void
  onSelectSession: (session: ChatSession) => void
  onSelectView: (view: View) => void
  profiles: Profile[]
  projects: Project[]
  sessions: ChatSession[]
  user: User
}) {
  const [drawerOpen, setDrawerOpen] = React.useState(false)
  const [collapsed, setCollapsed] = React.useState(false)
  const [railOpen, setRailOpen] = React.useState(false)
  return (
    <div className={`app-shell ${collapsed ? 'sidebar-collapsed' : ''} ${railOpen ? 'rail-open' : ''}`}>
      <MobileTopbar activeProfile={props.activeProfile} activeProject={props.activeProject} onMenu={() => setDrawerOpen(true)} onNewChat={() => props.onSelectView('chat')} />
      <aside className={`sidebar ${drawerOpen ? 'is-open' : ''}`}>
        <Sidebar {...props} collapsed={collapsed} onClose={() => setDrawerOpen(false)} onToggleCollapse={() => setCollapsed(v => !v)} />
      </aside>
      {drawerOpen && <button aria-label="Close menu" className="drawer-scrim" onClick={() => setDrawerOpen(false)} />}
      <main className="main-pane">
        <header className="main-header">
          <div><p className="eyebrow">{props.currentView}</p><h2>{props.activeProject?.name || 'Team workspace'}</h2></div>
          <div className="context-chips"><span>{props.user.username}</span><span>{props.activeProfile?.name || 'no profile'}</span><span>Hermes</span></div>
          <button className="icon-button rail-toggle" onClick={() => setRailOpen(v => !v)} aria-label="Toggle files">⌸</button>
        </header>
        {props.children}
      </main>
      {railOpen && <button aria-label="Close files" className="drawer-scrim rail-scrim" onClick={() => setRailOpen(false)} />}
      <RightRail activeProfile={props.activeProfile} activeProject={props.activeProject} activeSession={props.activeSession} projects={props.projects} />
    </div>
  )
}
