import React from 'react'
import type { FileEntry, Project } from '../../types'
import { listTree, mkdir, renamePath, deletePath, writeFile } from '../../api/files'
import { FileEditor } from './FileEditor'

function Node({ token, slug, dir, depth, onOpen, refreshKey }: { token: string; slug: string; dir: string; depth: number; onOpen: (path: string) => void; refreshKey: number }) {
  const [open, setOpen] = React.useState(depth === 0)
  const [entries, setEntries] = React.useState<FileEntry[]>([])
  const [loaded, setLoaded] = React.useState(false)

  const load = React.useCallback(() => {
    listTree(token, slug, dir).then(b => { setEntries(b.entries); setLoaded(true) }).catch(() => setLoaded(true))
  }, [token, slug, dir])

  React.useEffect(() => { if (open) load() }, [open, load, refreshKey])

  return <div className="tree-node">
    {entries.map(entry => {
      const path = dir ? `${dir}/${entry.name}` : entry.name
      return entry.type === 'dir'
        ? <Folder key={path} token={token} slug={slug} path={path} name={entry.name} depth={depth} onOpen={onOpen} refreshKey={refreshKey} />
        : <button key={path} className="tree-row file" style={{ paddingLeft: 8 + depth * 12 }} onClick={() => onOpen(path)}>📄 {entry.name}</button>
    })}
    {loaded && entries.length === 0 && depth === 0 && <p className="muted tree-empty">Empty project</p>}
  </div>
}

function Folder({ token, slug, path, name, depth, onOpen, refreshKey }: { token: string; slug: string; path: string; name: string; depth: number; onOpen: (path: string) => void; refreshKey: number }) {
  const [open, setOpen] = React.useState(false)
  return <div>
    <button className="tree-row dir" style={{ paddingLeft: 8 + depth * 12 }} onClick={() => setOpen(v => !v)}>{open ? '▾' : '▸'} 📁 {name}</button>
    {open && <Node token={token} slug={slug} dir={path} depth={depth + 1} onOpen={onOpen} refreshKey={refreshKey} />}
  </div>
}

export function WorkspaceTree({ token, project }: { token: string; project: Project | null }) {
  const [refreshKey, setRefreshKey] = React.useState(0)
  const [editing, setEditing] = React.useState<string | null>(null)
  const refresh = () => setRefreshKey(k => k + 1)

  if (!project) return <aside className="right-rail"><div className="rail-card"><p className="muted">Select a project to browse files.</p></div></aside>

  async function newFile() {
    const name = window.prompt('New file path (relative to project):')
    if (!name) return
    await writeFile(token, project!.slug, name, '').catch(() => undefined)
    refresh()
  }
  async function newFolder() {
    const name = window.prompt('New folder path:')
    if (!name) return
    await mkdir(token, project!.slug, name).catch(() => undefined)
    refresh()
  }
  async function rename() {
    const from = window.prompt('Rename from (path):'); if (!from) return
    const to = window.prompt('Rename to (path):'); if (!to) return
    await renamePath(token, project!.slug, from, to).catch(() => undefined)
    refresh()
  }
  async function remove() {
    const path = window.prompt('Delete path:'); if (!path) return
    if (!window.confirm(`Delete ${path}? This cannot be undone.`)) return
    await deletePath(token, project!.slug, path).catch(() => undefined)
    refresh()
  }

  return <aside className="right-rail">
    <div className="tree-toolbar"><strong>{project.name}</strong><div className="tree-actions"><button title="New file" onClick={() => void newFile()}>＋📄</button><button title="New folder" onClick={() => void newFolder()}>＋📁</button><button title="Rename" onClick={() => void rename()}>✎</button><button title="Delete" onClick={() => void remove()}>🗑</button></div></div>
    <div className="tree-scroll"><Node token={token} slug={project.slug} dir="" depth={0} onOpen={setEditing} refreshKey={refreshKey} /></div>
    {editing && <FileEditor token={token} slug={project.slug} path={editing} onClose={() => setEditing(null)} />}
  </aside>
}
