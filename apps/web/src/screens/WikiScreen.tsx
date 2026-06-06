import React from 'react'
import type { Project } from '../types'
import { WorkspaceTree } from '../components/files/WorkspaceTree'
import { wikiFs, projectFs } from '../api/fsAdapter'

// Wiki surface: a personal per-user wiki and (when a project is active) that
// project's shared `wiki/` folder. Both reuse the tree + CodeMirror editor.
export function WikiScreen({ token, activeProject }: { token: string; activeProject: Project | null }) {
  const [source, setSource] = React.useState<'personal' | 'project'>('personal')
  const useProject = source === 'project' && !!activeProject
  const fs = React.useMemo(
    () => (useProject && activeProject ? projectFs(token, activeProject.slug, 'wiki') : wikiFs(token)),
    [token, useProject, activeProject?.slug]
  )
  const title = useProject && activeProject ? `${activeProject.name} · wiki` : 'My Wiki'

  return <section className="wiki-view">
    <div className="wiki-switch">
      <button className={source === 'personal' ? 'active' : ''} onClick={() => setSource('personal')}>My Wiki</button>
      <button className={source === 'project' ? 'active' : ''} onClick={() => setSource('project')} disabled={!activeProject} title={activeProject ? undefined : 'Select a project first'}>{activeProject ? `${activeProject.name} wiki` : 'Project wiki'}</button>
      {useProject && activeProject?.visibility === 'shared' && <span className="wiki-hint">Shared · all members can edit</span>}
    </div>
    <WorkspaceTree key={title} fs={fs} title={title} className="wiki-pane" />
  </section>
}
