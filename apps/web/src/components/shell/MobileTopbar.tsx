import type { Profile, Project } from '../../types'
import { IconMenu, IconNewChat, IconPanelRight } from './icons'

export function MobileTopbar({ activeProject, activeProfile, onMenu, onNewChat, onFiles }: { activeProject: Project | null; activeProfile: Profile | null; onMenu: () => void; onNewChat: () => void; onFiles: () => void }) {
  return <header className="mobile-topbar"><button className="icon-button" onClick={onMenu} aria-label="Menu"><IconMenu size={18} /></button><div className="mobile-context"><strong>{activeProject?.name || 'Hive OS'}</strong><span>{activeProfile?.name || 'Hermes profile'}</span></div><div className="mobile-actions"><button className="icon-button" onClick={onFiles} aria-label="Files"><IconPanelRight size={18} /></button><button className="icon-button" onClick={onNewChat} aria-label="New chat"><IconNewChat size={18} /></button></div></header>
}
