import React from 'react'
import type { ChatSession, Profile, Project, User, View } from '../../types'
import { Sidebar } from './Sidebar'
import { MobileTopbar } from './MobileTopbar'
import { RightRail } from './RightRail'

const matches = (query: string) => typeof window !== 'undefined' && window.matchMedia(query).matches
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))
const stored = (key: string, fallback: number) => {
  const raw = typeof localStorage !== 'undefined' ? localStorage.getItem(key) : null
  const n = raw == null ? NaN : Number(raw)
  return Number.isFinite(n) ? n : fallback
}

const LEFT_MIN = 200, LEFT_MAX = 480
const RIGHT_MIN = 220, RIGHT_MAX = 600

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
  const [railOpen, setRailOpen] = React.useState(false)
  const [leftWidth, setLeftWidth] = React.useState(() => stored('hive.leftWidth', 294))
  const [rightWidth, setRightWidth] = React.useState(() => stored('hive.rightWidth', 292))
  const [rightHidden, setRightHidden] = React.useState(() => (typeof localStorage !== 'undefined' && localStorage.getItem('hive.rightHidden') === '1'))

  React.useEffect(() => { localStorage.setItem('hive.leftWidth', String(leftWidth)) }, [leftWidth])
  React.useEffect(() => { localStorage.setItem('hive.rightWidth', String(rightWidth)) }, [rightWidth])
  React.useEffect(() => { localStorage.setItem('hive.rightHidden', rightHidden ? '1' : '0') }, [rightHidden])

  const toggleRight = () => { if (matches('(min-width: 1280px)')) setRightHidden(v => !v); else setRailOpen(v => !v) }

  function startResize(side: 'left' | 'right') {
    return (event: React.MouseEvent) => {
      event.preventDefault()
      const startX = event.clientX
      const startLeft = leftWidth
      const startRight = rightWidth
      const onMove = (e: MouseEvent) => {
        if (side === 'left') setLeftWidth(clamp(startLeft + (e.clientX - startX), LEFT_MIN, LEFT_MAX))
        else setRightWidth(clamp(startRight - (e.clientX - startX), RIGHT_MIN, RIGHT_MAX))
      }
      const onUp = () => {
        window.removeEventListener('mousemove', onMove)
        window.removeEventListener('mouseup', onUp)
        document.body.style.userSelect = ''
        document.body.style.cursor = ''
      }
      document.body.style.userSelect = 'none'
      document.body.style.cursor = 'col-resize'
      window.addEventListener('mousemove', onMove)
      window.addEventListener('mouseup', onUp)
    }
  }

  const shellStyle = {
    ['--left-w']: `${leftWidth}px`,
    ['--right-w']: `${rightHidden ? 0 : rightWidth}px`,
  } as React.CSSProperties

  return (
    <div className={`app-shell ${railOpen ? 'rail-open' : ''} ${rightHidden ? 'right-hidden' : ''}`} style={shellStyle}>
      <MobileTopbar activeProfile={props.activeProfile} activeProject={props.activeProject} onMenu={() => setDrawerOpen(true)} onNewChat={() => props.onSelectView('chat')} />
      <aside className={`sidebar ${drawerOpen ? 'is-open' : ''}`}>
        <Sidebar {...props} onClose={() => setDrawerOpen(false)} />
      </aside>
      <div className="resize-handle resize-left" style={{ left: 'var(--left-w)' }} onMouseDown={startResize('left')} role="separator" aria-label="Resize sidebar" />
      {drawerOpen && <button aria-label="Close menu" className="drawer-scrim" onClick={() => setDrawerOpen(false)} />}
      <main className="main-pane">
        <header className="main-header">
          <div><p className="eyebrow">{props.currentView}</p><h2>{props.activeProject?.name || 'Team workspace'}</h2></div>
          <div className="header-right">
            <div className="context-chips"><span>{props.user.username}</span><span>{props.activeProfile?.name || 'no profile'}</span><span>Hermes</span></div>
            <button className="icon-button panel-toggle rail-toggle" onClick={toggleRight} aria-label="Toggle files" title="Toggle files panel">◨</button>
          </div>
        </header>
        {props.children}
      </main>
      <div className="resize-handle resize-right" style={{ right: 'var(--right-w)' }} onMouseDown={startResize('right')} role="separator" aria-label="Resize files panel" />
      {railOpen && <button aria-label="Close files" className="drawer-scrim rail-scrim" onClick={() => setRailOpen(false)} />}
      <RightRail token={props.token} activeProfile={props.activeProfile} activeProject={props.activeProject} activeSession={props.activeSession} projects={props.projects} />
    </div>
  )
}
