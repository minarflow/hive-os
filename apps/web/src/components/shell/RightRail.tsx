import React from 'react'
import type { ChatSession, Profile, Project } from '../../types'
import { WorkspaceTree } from '../files/WorkspaceTree'
import { projectFs } from '../../api/fsAdapter'

export function RightRail({ token, activeProject }: { token: string; activeProfile: Profile | null; activeProject: Project | null; activeSession: ChatSession | null; projects: Project[] }) {
  const fs = React.useMemo(() => activeProject ? projectFs(token, activeProject.slug) : null, [token, activeProject?.slug])
  if (!fs || !activeProject) return <aside className="right-rail"><div className="rail-card"><p className="muted">Select a project to browse files.</p></div></aside>
  return <WorkspaceTree fs={fs} title={activeProject.name} className="right-rail" />
}
