import React from 'react'
import type { Project } from '../types'
import { WorkspaceTree } from '../components/files/WorkspaceTree'
import { wikiFs, projectFs } from '../api/fsAdapter'
import { listAll as wikiListAll, type WikiNoteRaw } from '../api/wiki'
import { projectWikiAll } from '../api/files'
import { buildWikiModel } from '../components/wiki/wikiGraph'
import { WikiSearch } from '../components/wiki/WikiSearch'

const WikiGraph = React.lazy(() => import('../components/wiki/WikiGraph').then(m => ({ default: m.WikiGraph })))
const WikiNote = React.lazy(() => import('../components/wiki/WikiNote').then(m => ({ default: m.WikiNote })))

type Tab = 'files' | 'graph' | 'search'

export function WikiScreen({ token, activeProject }: { token: string; activeProject: Project | null }) {
  const [source, setSource] = React.useState<'personal' | 'project'>('personal')
  const [tab, setTab] = React.useState<Tab>('files')
  const [openNote, setOpenNote] = React.useState<string | null>(null)
  const [notes, setNotes] = React.useState<WikiNoteRaw[]>([])
  const [version, setVersion] = React.useState(0)

  const useProject = source === 'project' && !!activeProject
  const fs = React.useMemo(() => (useProject && activeProject ? projectFs(token, activeProject.slug, 'wiki') : wikiFs(token)), [token, useProject, activeProject?.slug])
  const loadAll = React.useCallback(() => (useProject && activeProject ? projectWikiAll(token, activeProject.slug) : wikiListAll(token)), [token, useProject, activeProject?.slug])

  React.useEffect(() => { setOpenNote(null) }, [fs])
  React.useEffect(() => {
    let alive = true
    loadAll().then(b => { if (alive) setNotes(b.notes) }).catch(() => { if (alive) setNotes([]) })
    return () => { alive = false }
  }, [loadAll, version])

  const model = React.useMemo(() => buildWikiModel(notes), [notes])
  const title = useProject && activeProject ? `${activeProject.name} · wiki` : 'My Wiki'
  const reload = () => setVersion(v => v + 1)
  const openInFiles = (p: string) => { setOpenNote(p); setTab('files') }

  return <section className="wiki-view">
    <div className="wiki-switch">
      <div className="seg">
        <button className={source === 'personal' ? 'active' : ''} onClick={() => setSource('personal')}>My Wiki</button>
        <button className={source === 'project' ? 'active' : ''} onClick={() => setSource('project')} disabled={!activeProject} title={activeProject ? undefined : 'Select a project first'}>{activeProject ? activeProject.name : 'Project'} wiki</button>
      </div>
      <div className="seg tabs">
        <button className={tab === 'files' ? 'active' : ''} onClick={() => setTab('files')}>Files</button>
        <button className={tab === 'graph' ? 'active' : ''} onClick={() => setTab('graph')}>Graph</button>
        <button className={tab === 'search' ? 'active' : ''} onClick={() => setTab('search')}>Search</button>
      </div>
      {useProject && activeProject?.visibility === 'shared' && <span className="wiki-hint">Shared · all members edit</span>}
    </div>

    {tab === 'files' && <div className="wiki-files">
      <WorkspaceTree key={title} fs={fs} title={title} className="wiki-tree" onOpenFile={setOpenNote} onChange={reload} activePath={openNote} />
      <div className="wiki-main">
        {openNote
          ? <React.Suspense fallback={<div className="wiki-pane-msg muted">Loading note…</div>}><WikiNote fs={fs} path={openNote} backlinks={model.backlinks[openNote] || []} resolve={model.resolve} onOpenNote={openInFiles} onClose={() => setOpenNote(null)} onSaved={reload} /></React.Suspense>
          : <div className="wiki-placeholder"><p className="muted">Select or create a note. Link notes with <code>[[Note]]</code> — backlinks &amp; graph update automatically.</p></div>}
      </div>
    </div>}

    {tab === 'graph' && <React.Suspense fallback={<div className="wiki-pane-msg muted">Loading graph…</div>}><WikiGraph nodes={model.nodes} links={model.links} activePath={openNote} onOpen={openInFiles} /></React.Suspense>}

    {tab === 'search' && <WikiSearch notes={notes} onOpen={openInFiles} />}
  </section>
}
