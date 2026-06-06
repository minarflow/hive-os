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

export function WikiScreen({ token, projects }: { token: string; projects: Project[] }) {
  const [sourceKey, setSourceKey] = React.useState<string>('')   // '' = My Wiki, else project slug
  const [tab, setTab] = React.useState<Tab>('files')
  const [openNote, setOpenNote] = React.useState<string | null>(null)
  const [notes, setNotes] = React.useState<WikiNoteRaw[]>([])
  const [version, setVersion] = React.useState(0)

  const selected = projects.find(p => p.slug === sourceKey) || null
  const fs = React.useMemo(() => (selected ? projectFs(token, selected.slug, 'wiki') : wikiFs(token)), [token, selected?.slug])
  const loadAll = React.useCallback(() => (selected ? projectWikiAll(token, selected.slug) : wikiListAll(token)), [token, selected?.slug])

  React.useEffect(() => { setOpenNote(null) }, [fs])
  React.useEffect(() => {
    let alive = true
    loadAll().then(b => { if (alive) setNotes(b.notes) }).catch(() => { if (alive) setNotes([]) })
    return () => { alive = false }
  }, [loadAll, version])

  const mdNotes = React.useMemo(() => notes.filter(n => /\.(md|markdown)$/i.test(n.path)), [notes])
  const model = React.useMemo(() => buildWikiModel(mdNotes), [mdNotes])
  const isMd = (name: string) => /\.(md|markdown)$/i.test(name)
  const title = selected ? `${selected.name} · wiki` : 'My Wiki'
  const reload = () => setVersion(v => v + 1)
  const openInFiles = (p: string) => { setOpenNote(p); setTab('files') }

  return <section className="wiki-view">
    <div className="wiki-switch">
      <label className="wiki-source">
        <select value={sourceKey} onChange={e => setSourceKey(e.target.value)}>
          <option value="">📒 My Wiki</option>
          {projects.length > 0 && <optgroup label="Project wikis">
            {projects.map(p => <option key={p.slug} value={p.slug}>{p.name} · {p.visibility}</option>)}
          </optgroup>}
        </select>
      </label>
      <div className="seg tabs">
        <button className={tab === 'files' ? 'active' : ''} onClick={() => setTab('files')}>Files</button>
        <button className={tab === 'graph' ? 'active' : ''} onClick={() => setTab('graph')}>Graph</button>
        <button className={tab === 'search' ? 'active' : ''} onClick={() => setTab('search')}>Search</button>
      </div>
      {selected?.visibility === 'shared' && <span className="wiki-hint">Shared · all members edit</span>}
    </div>

    {tab === 'files' && <div className="wiki-files">
      <WorkspaceTree key={title} fs={fs} title={title} className="wiki-tree" onOpenFile={setOpenNote} onChange={reload} activePath={openNote} fileFilter={isMd} defaultExt="md" />
      <div className="wiki-main">
        {openNote
          ? <React.Suspense fallback={<div className="wiki-pane-msg muted">Loading note…</div>}><WikiNote fs={fs} path={openNote} backlinks={model.backlinks[openNote] || []} resolve={model.resolve} onOpenNote={openInFiles} onClose={() => setOpenNote(null)} onSaved={reload} /></React.Suspense>
          : <div className="wiki-placeholder"><p className="muted">Select or create a note. Link notes with <code>[[Note]]</code> — backlinks &amp; graph update automatically.</p></div>}
      </div>
    </div>}

    {tab === 'graph' && <React.Suspense fallback={<div className="wiki-pane-msg muted">Loading graph…</div>}><WikiGraph nodes={model.nodes} links={model.links} activePath={openNote} onOpen={openInFiles} /></React.Suspense>}

    {tab === 'search' && <WikiSearch notes={mdNotes} onOpen={openInFiles} />}
  </section>
}
