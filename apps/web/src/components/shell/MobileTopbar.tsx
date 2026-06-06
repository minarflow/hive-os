import type { Profile, Project } from '../../types'
import { IconMenu, IconNewChat } from './icons'

export function MobileTopbar({ activeProject, activeProfile, onMenu, onNewChat }: { activeProject: Project | null; activeProfile: Profile | null; onMenu: () => void; onNewChat: () => void }) {
  return <header className="mobile-topbar"><button className="icon-button" onClick={onMenu} aria-label="Menu"><IconMenu size={18} /></button><div className="mobile-context"><strong>{activeProject?.name || 'Hive OS'}</strong><span>{activeProfile?.name || 'Hermes profile'}</span></div><button className="icon-button" onClick={onNewChat} aria-label="New chat"><IconNewChat size={18} /></button></header>
}
