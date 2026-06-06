import type { Profile, Project } from '../../types'

export function MobileTopbar({ activeProject, activeProfile, onMenu, onNewChat }: { activeProject: Project | null; activeProfile: Profile | null; onMenu: () => void; onNewChat: () => void }) {
  return <header className="mobile-topbar"><button className="icon-button" onClick={onMenu}>☰</button><div className="mobile-context"><strong>{activeProject?.name || 'Hive OS'}</strong><span>{activeProfile?.name || 'Hermes profile'}</span></div><button className="icon-button" onClick={onNewChat}>＋</button></header>
}
