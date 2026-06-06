import React from 'react'
import type { FileEntry, Project } from '../../types'
import { listTree, mkdir, renamePath, deletePath, writeFile } from '../../api/files'
import { IconFile, IconFolder, IconChevronRight, IconFilePlus, IconFolderPlus } from '../shell/icons'

// Lazy-load the CodeMirror editor so its chunk only loads when a file is opened.
const FileEditor = React.lazy(() => import('./FileEditor').then(m => ({ default: m.FileEditor })))

type Ctl = {
  token: string; slug: string; refreshKey: number
  expanded: Set<string>; toggle: (p: string) => void
  creating: { dir: string; type: 'file' | 'dir' } | null
  renaming: string | null
  activePath: string | null
  openFile: (p: string) => void
  openMenu: (e: React.MouseEvent, path: string | null, isDir: boolean) => void
  submitCreate: (name: string) => void
  cancelCreate: () => void
  submitRename: (path: string, name: string) => void
  cancelRename: () => void
}

const base = (p: string) => p.split('/').pop() || p

function InlineInput({ initial, icon, depth, onSubmit, onCancel }: { initial: string; icon: React.ReactNode; depth: number; onSubmit: (v: string) => void; onCancel: () => void }) {
  const [v, setV] = React.useState(initial)
  const done = React.useRef(false)
  const finish = (commit: boolean) => {
    if (done.current) return
    done.current = true
    if (commit && v.trim() && v.trim() !== initial) onSubmit(v.trim()); else onCancel()
  }
  return <div className="tree-row inline" style={{ paddingLeft: 8 + depth * 12 }}>
    <span className="tree-ico">{icon}</span>
    <input autoFocus className="tree-input" value={v} onChange={e => setV(e.target.value)}
      onKeyDown={e => { if (e.key === 'Enter') finish(true); else if (e.key === 'Escape') finish(false) }}
      onBlur={() => finish(true)} />
  </div>
}

function Level({ dir, depth, t }: { dir: string; depth: number; t: Ctl }) {
  const [entries, setEntries] = React.useState<FileEntry[]>([])
  const [loaded, setLoaded] = React.useState(false)
  React.useEffect(() => {
    let alive = true
    listTree(t.token, t.slug, dir).then(b => { if (alive) { setEntries(b.entries); setLoaded(true) } }).catch(() => { if (alive) setLoaded(true) })
    return () => { alive = false }
  }, [t.token, t.slug, dir, t.refreshKey])

  return <div className="tree-level">
    {t.creating && t.creating.dir === dir && <InlineInput initial="" depth={depth} icon={t.creating.type === 'dir' ? <IconFolder size={15} /> : <IconFile size={15} />} onSubmit={t.submitCreate} onCancel={t.cancelCreate} />}
    {entries.map(entry => {
      const path = dir ? `${dir}/${entry.name}` : entry.name
      if (t.renaming === path) return <InlineInput key={path} initial={entry.name} depth={depth} icon={entry.type === 'dir' ? <IconFolder size={15} /> : <IconFile size={15} />} onSubmit={n => t.submitRename(path, n)} onCancel={t.cancelRename} />
      if (entry.type === 'dir') {
        const open = t.expanded.has(path)
        return <div key={path}>
          <button className="tree-row dir" style={{ paddingLeft: 8 + depth * 12 }} onClick={() => t.toggle(path)} onContextMenu={e => t.openMenu(e, path, true)}>
            <span className={`tree-chevron ${open ? 'open' : ''}`}><IconChevronRight size={13} /></span>
            <span className="tree-ico"><IconFolder size={15} /></span>
            <span className="tree-name">{entry.name}</span>
          </button>
          {open && <Level dir={path} depth={depth + 1} t={t} />}
        </div>
      }
      return <button key={path} className={`tree-row file ${t.activePath === path ? 'active' : ''}`} style={{ paddingLeft: 8 + depth * 12 }} onClick={() => t.openFile(path)} onContextMenu={e => t.openMenu(e, path, false)}>
        <span className="tree-ico"><IconFile size={15} /></span>
        <span className="tree-name">{entry.name}</span>
      </button>
    })}
    {loaded && entries.length === 0 && depth === 0 && !t.creating && <p className="muted tree-empty">Empty project · right-click to add</p>}
  </div>
}

export function WorkspaceTree({ token, project }: { token: string; project: Project | null }) {
  const [refreshKey, setRefreshKey] = React.useState(0)
  const [editing, setEditing] = React.useState<string | null>(null)
  const [treeError, setTreeError] = React.useState<string | null>(null)
  const [expanded, setExpanded] = React.useState<Set<string>>(new Set())
  const [creating, setCreating] = React.useState<{ dir: string; type: 'file' | 'dir' } | null>(null)
  const [renaming, setRenaming] = React.useState<string | null>(null)
  const [menu, setMenu] = React.useState<{ x: number; y: number; path: string | null; isDir: boolean } | null>(null)
  const refresh = () => setRefreshKey(k => k + 1)
  const slug = project?.slug || ''

  React.useEffect(() => {
    const onChange = () => setRefreshKey(k => k + 1)
    window.addEventListener('hive:files-changed', onChange)
    return () => window.removeEventListener('hive:files-changed', onChange)
  }, [])
  React.useEffect(() => {
    if (!menu) return
    const close = () => setMenu(null)
    window.addEventListener('click', close)
    window.addEventListener('scroll', close, true)
    return () => { window.removeEventListener('click', close); window.removeEventListener('scroll', close, true) }
  }, [menu])

  if (!project) return <aside className="right-rail"><div className="rail-card"><p className="muted">Select a project to browse files.</p></div></aside>

  const guard = async (p: Promise<unknown>) => { setTreeError(null); try { await p } catch (e) { setTreeError(String(e)) } refresh() }

  function startCreate(dir: string, type: 'file' | 'dir') {
    setRenaming(null)
    if (dir) setExpanded(s => new Set(s).add(dir))
    setCreating({ dir, type })
  }
  async function submitCreate(name: string) {
    const c = creating; if (!c) return
    setCreating(null)
    const full = c.dir ? `${c.dir}/${name}` : name
    if (c.type === 'dir') await guard(mkdir(token, slug, full))
    else { await guard(writeFile(token, slug, full, '')); setEditing(full) }
  }
  async function submitRename(path: string, name: string) {
    setRenaming(null)
    const parent = path.split('/').slice(0, -1).join('/')
    const to = parent ? `${parent}/${name}` : name
    if (to === path) return
    await guard(renamePath(token, slug, path, to))
    if (editing === path) setEditing(to)
  }
  async function remove(path: string) {
    if (!window.confirm(`Delete "${base(path)}"? This cannot be undone.`)) return
    await guard(deletePath(token, slug, path))
    if (editing === path || (editing && editing.startsWith(path + '/'))) setEditing(null)
  }

  const t: Ctl = {
    token, slug, refreshKey, expanded,
    toggle: p => setExpanded(s => { const n = new Set(s); if (n.has(p)) n.delete(p); else n.add(p); return n }),
    creating, renaming, activePath: editing,
    openFile: setEditing,
    openMenu: (e, path, isDir) => { e.preventDefault(); e.stopPropagation(); setMenu({ x: e.clientX, y: e.clientY, path, isDir }) },
    submitCreate, cancelCreate: () => setCreating(null),
    submitRename, cancelRename: () => setRenaming(null)
  }

  const menuDir = menu ? (menu.path == null ? '' : menu.isDir ? menu.path : menu.path.split('/').slice(0, -1).join('/')) : ''

  return <aside className="right-rail">
    <div className="tree-toolbar"><strong>{project.name}</strong><div className="tree-actions">
      <button title="New file" aria-label="New file" onClick={() => startCreate('', 'file')}><IconFilePlus size={16} /></button>
      <button title="New folder" aria-label="New folder" onClick={() => startCreate('', 'dir')}><IconFolderPlus size={16} /></button>
    </div></div>
    {treeError && <p className="tree-error">{treeError}</p>}
    <div className="tree-scroll" onContextMenu={e => { if (e.target === e.currentTarget) t.openMenu(e, null, true) }}><Level dir="" depth={0} t={t} /></div>
    {editing && <React.Suspense fallback={<div className="file-editor"><div className="file-editor-head"><strong>{base(editing)}</strong></div><p className="muted" style={{ padding: '10px' }}>Loading editor…</p></div>}><FileEditor token={token} slug={slug} path={editing} onClose={() => setEditing(null)} /></React.Suspense>}
    {menu && <div className="ctx-menu" style={{ top: menu.y, left: menu.x }} onClick={e => e.stopPropagation()}>
      <button onClick={() => { startCreate(menuDir, 'file'); setMenu(null) }}>New File</button>
      <button onClick={() => { startCreate(menuDir, 'dir'); setMenu(null) }}>New Folder</button>
      {menu.path != null && <><div className="ctx-sep" /><button onClick={() => { setRenaming(menu.path); setMenu(null) }}>Rename</button><button className="danger" onClick={() => { const p = menu.path as string; setMenu(null); void remove(p) }}>Delete</button></>}
    </div>}
  </aside>
}
