import React from 'react'
import type { ChatSession, Profile, Project, User, View } from '../../types'
import { Sidebar } from './Sidebar'
import { MobileTopbar } from './MobileTopbar'
import { RightRail } from './RightRail'

const matches = (query: string) => typeof window !== 'undefined' && window.matchMedia(query).matches

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
  token: string
  user: User
}) {
  const [drawerOpen, setDrawerOpen] = React.useState(false)
  const [collapsed, setCollapsed] = React.useState(false)
  const [railOpen, setRailOpen] = React.useState(false)
  const [leftHidden, setLeftHidden] = React.useState(false)
  const [rightHidden, setRightHidden] = React.useState(false)

  // One button per side. On wide layouts it fully hides/shows the pane; on
  // narrow layouts it falls back to the drawer (left) / overlay (right).
  const toggleLeft = () => { if (matches('(min-width: 768px)')) setLeftHidden(v => !v); else setDrawerOpen(v => !v) }
  const toggleRight = () => { if (matches('(min-width: 1280px)')) setRightHidden(v => !v); else setRailOpen(v => !v) }

  return (
    <div className={`app-shell ${collapsed ? 'sidebar-collapsed' : ''} ${railOpen ? 'rail-open' : ''} ${leftHidden ? 'left-hidden' : ''} ${rightHidden ? 'right-hidden' : ''}`}>
      <MobileTopbar activeProfile={props.activeProfile} activeProject={props.activeProject} onMenu={() => setDrawerOpen(true)} onNewChat={() => props.onSelectView('chat')} />
      <aside className={`sidebar ${drawerOpen ? 'is-open' : ''}`}>
        <Sidebar {...props} collapsed={collapsed} onClose={() => setDrawerOpen(false)} onToggleCollapse={() => setCollapsed(v => !v)} />
      </aside>
      {drawerOpen && <button aria-label="Close menu" className="drawer-scrim" onClick={() => setDrawerOpen(false)} />}
      <main className="main-pane">
        <header className="main-header">
          <div className="header-left">
            <button className="icon-button panel-toggle" onClick={toggleLeft} aria-label="Toggle sidebar" title="Toggle sidebar">◧</button>
            <div><p className="eyebrow">{props.currentView}</p><h2>{props.activeProject?.name || 'Team workspace'}</h2></div>
          </div>
          <div className="header-right">
            <div className="context-chips"><span>{props.user.username}</span><span>{props.activeProfile?.name || 'no profile'}</span><span>Hermes</span></div>
            <button className="icon-button panel-toggle rail-toggle" onClick={toggleRight} aria-label="Toggle files" title="Toggle files panel">◨</button>
          </div>
        </header>
        {props.children}
      </main>
      {railOpen && <button aria-label="Close files" className="drawer-scrim rail-scrim" onClick={() => setRailOpen(false)} />}
      <RightRail token={props.token} activeProfile={props.activeProfile} activeProject={props.activeProject} activeSession={props.activeSession} projects={props.projects} />
    </div>
  )
}
