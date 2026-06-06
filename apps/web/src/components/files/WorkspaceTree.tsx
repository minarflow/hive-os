import React from 'react'
import type { FileEntry, Project } from '../../types'
import { listTree, mkdir, renamePath, deletePath, writeFile } from '../../api/files'
import { FileEditor } from './FileEditor'
import { IconFile, IconFolder, IconChevronRight, IconFilePlus, IconFolderPlus, IconPencil, IconTrash } from '../shell/icons'

function Node({ token, slug, dir, depth, onOpen, refreshKey }: { token: string; slug: string; dir: string; depth: number; onOpen: (path: string) => void; refreshKey: number }) {
  const [entries, setEntries] = React.useState<FileEntry[]>([])
  const [loaded, setLoaded] = React.useState(false)

  const load = React.useCallback(() => {
    listTree(token, slug, dir).then(b => { setEntries(b.entries); setLoaded(true) }).catch(() => setLoaded(true))
  }, [token, slug, dir])

  React.useEffect(() => { load() }, [load, refreshKey])

  return <div className="tree-node">
    {entries.map(entry => {
      const path = dir ? `${dir}/${entry.name}` : entry.name
      return entry.type === 'dir'
        ? <Folder key={path} token={token} slug={slug} path={path} name={entry.name} depth={depth} onOpen={onOpen} refreshKey={refreshKey} />
        : <button key={path} className="tree-row file" style={{ paddingLeft: 8 + depth * 12 }} onClick={() => onOpen(path)}><span className="tree-ico"><IconFile size={15} /></span><span className="tree-name">{entry.name}</span></button>
    })}
    {loaded && entries.length === 0 && depth === 0 && <p className="muted tree-empty">Empty project</p>}
  </div>
}

function Folder({ token, slug, path, name, depth, onOpen, refreshKey }: { token: string; slug: string; path: string; name: string; depth: number; onOpen: (path: string) => void; refreshKey: number }) {
  const [open, setOpen] = React.useState(false)
  return <div>
    <button className="tree-row dir" style={{ paddingLeft: 8 + depth * 12 }} onClick={() => setOpen(v => !v)}><span className={`tree-chevron ${open ? 'open' : ''}`}><IconChevronRight size={13} /></span><span className="tree-ico"><IconFolder size={15} /></span><span className="tree-name">{name}</span></button>
    {open && <Node token={token} slug={slug} dir={path} depth={depth + 1} onOpen={onOpen} refreshKey={refreshKey} />}
  </div>
}

export function WorkspaceTree({ token, project }: { token: string; project: Project | null }) {
  const [refreshKey, setRefreshKey] = React.useState(0)
  const [editing, setEditing] = React.useState<string | null>(null)
  const [treeError, setTreeError] = React.useState<string | null>(null)
  const refresh = () => setRefreshKey(k => k + 1)

  // Auto-refresh the tree when a chat run finishes (Hermes may have written files).
  React.useEffect(() => {
    const onChange = () => setRefreshKey(k => k + 1)
    window.addEventListener('hive:files-changed', onChange)
    return () => window.removeEventListener('hive:files-changed', onChange)
  }, [])

  if (!project) return <aside className="right-rail"><div className="rail-card"><p className="muted">Select a project to browse files.</p></div></aside>

  async function newFile() {
    setTreeError(null)
    const name = window.prompt('New file path (relative to project):')
    if (!name) return
    await writeFile(token, project!.slug, name, '').catch(e => { setTreeError(String(e)); return undefined })
    refresh()
  }
  async function newFolder() {
    setTreeError(null)
    const name = window.prompt('New folder path:')
    if (!name) return
    await mkdir(token, project!.slug, name).catch(e => { setTreeError(String(e)); return undefined })
    refresh()
  }
  async function rename() {
    setTreeError(null)
    const from = window.prompt('Rename from (path):'); if (!from) return
    const to = window.prompt('Rename to (path):'); if (!to) return
    await renamePath(token, project!.slug, from, to).catch(e => { setTreeError(String(e)); return undefined })
    refresh()
  }
  async function remove() {
    setTreeError(null)
    const path = window.prompt('Delete path:'); if (!path) return
    if (!window.confirm(`Delete ${path}? This cannot be undone.`)) return
    await deletePath(token, project!.slug, path).catch(e => { setTreeError(String(e)); return undefined })
    refresh()
  }

  return <aside className="right-rail">
    <div className="tree-toolbar"><strong>{project.name}</strong><div className="tree-actions"><button title="New file" aria-label="New file" onClick={() => void newFile()}><IconFilePlus size={16} /></button><button title="New folder" aria-label="New folder" onClick={() => void newFolder()}><IconFolderPlus size={16} /></button><button title="Rename" aria-label="Rename" onClick={() => void rename()}><IconPencil size={16} /></button><button title="Delete" aria-label="Delete" onClick={() => void remove()}><IconTrash size={16} /></button></div></div>
    {treeError && <p className="tree-error">{treeError}</p>}
    <div className="tree-scroll"><Node token={token} slug={project.slug} dir="" depth={0} onOpen={setEditing} refreshKey={refreshKey} /></div>
    {editing && <FileEditor token={token} slug={project.slug} path={editing} onClose={() => setEditing(null)} />}
  </aside>
}
