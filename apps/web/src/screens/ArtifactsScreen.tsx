import React from 'react'
import type { Project } from '../types'
import { WorkspaceTree } from '../components/files/WorkspaceTree'
import { FileEditor } from '../components/files/FileEditor'
import { projectFs } from '../api/fsAdapter'
import { fetchRawBlob } from '../api/files'
import { MessageContent } from '../components/chat/MessageContent'
import { Dropdown } from '../components/ui/Dropdown'

const clean = (n: string) => n.replace(/\s*\(private\)\s*$/i, '')
const IMG = /\.(png|jpe?g|gif|webp|svg|bmp|ico|avif)$/i
const HTML = /\.html?$/i
const MD = /\.(md|markdown)$/i
const previewUrl = (token: string, slug: string, path: string) =>
  `/api/preview/${encodeURIComponent(token)}/${encodeURIComponent(slug)}/${path.split('/').map(encodeURIComponent).join('/')}`

// Right pane: edit (CodeMirror) for any text file; rendered Preview for html/md; image for images.
function FileView({ token, slug, path, fs, onClose }: { token: string; slug: string; path: string; fs: ReturnType<typeof projectFs>; onClose: () => void }) {
  const name = path.split('/').pop() || path
  const previewable = HTML.test(path) || MD.test(path)
  const [mode, setMode] = React.useState<'preview' | 'source'>(previewable ? 'preview' : 'source')
  const [img, setImg] = React.useState<string | null>(null)
  const [md, setMd] = React.useState<string | null>(null)

  React.useEffect(() => { setMode(HTML.test(path) || MD.test(path) ? 'preview' : 'source') }, [path])

  React.useEffect(() => {
    let url: string | null = null
    setImg(null); setMd(null)
    if (IMG.test(path)) fetchRawBlob(token, slug, path).then(u => { url = u; setImg(u) }).catch(() => {})
    else if (MD.test(path) && mode === 'preview') fs.read(path).then(b => setMd(b.content)).catch(() => setMd(''))
    return () => { if (url) URL.revokeObjectURL(url) }
  }, [token, slug, path, mode, fs])

  if (IMG.test(path)) return <div className="file-editor"><div className="file-editor-head"><strong>{name}</strong><button className="ghost-button" onClick={onClose}>Close</button></div><div className="file-preview img">{img && <img src={img} alt={name} />}</div></div>

  if (mode === 'source') return <FileEditor fs={fs} path={path} onClose={previewable ? () => setMode('preview') : onClose} />

  // preview mode (html / md)
  return <div className="file-editor">
    <div className="file-editor-head">
      <strong title={path}>{name}</strong>
      <div className="seg sm"><button className="active">Preview</button><button onClick={() => setMode('source')}>Source</button></div>
      <button className="ghost-button" onClick={onClose}>Close</button>
    </div>
    {HTML.test(path)
      ? <iframe className="file-preview-frame" title={name} src={previewUrl(token, slug, path)} sandbox="allow-scripts allow-same-origin" />
      : <div className="file-preview md-doc"><div className="md">{md != null ? <MessageContent content={md} /> : <p className="muted">Loading…</p>}</div></div>}
  </div>
}

export function ArtifactsScreen({ token, projects, activeProject, pendingFile, onPendingConsumed }: { token: string; projects: Project[]; activeProject: Project | null; pendingFile?: { slug: string; path: string } | null; onPendingConsumed?: () => void }) {
  const [slug, setSlug] = React.useState(activeProject?.slug || projects[0]?.slug || '')
  const [path, setPath] = React.useState<string | null>(null)
  const [treeW, setTreeW] = React.useState(() => Number(localStorage.getItem('hive.filesTreeW')) || 260)
  const project = projects.find(p => p.slug === slug) || null
  const fs = React.useMemo(() => project ? projectFs(token, project.slug) : null, [token, project?.slug])

  React.useEffect(() => { localStorage.setItem('hive.filesTreeW', String(treeW)) }, [treeW])
  function startResize(e: React.MouseEvent) {
    e.preventDefault()
    const startX = e.clientX, startW = treeW
    const move = (ev: MouseEvent) => setTreeW(Math.min(560, Math.max(180, startW + (ev.clientX - startX))))
    const up = () => { window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up); document.body.style.cursor = ''; document.body.style.userSelect = '' }
    document.body.style.cursor = 'col-resize'; document.body.style.userSelect = 'none'
    window.addEventListener('mousemove', move); window.addEventListener('mouseup', up)
  }

  React.useEffect(() => { setPath(null) }, [slug])
  React.useEffect(() => {
    if (!pendingFile) return
    setSlug(pendingFile.slug); setPath(pendingFile.path); onPendingConsumed?.()
  }, [pendingFile])

  if (projects.length === 0) return <section className="placeholder-view"><div className="assistant-bubble compact"><h1>Files</h1><p>No projects yet.</p></div></section>

  return <section className="files-view">
    <div className="files-head">
      <Dropdown value={slug} onChange={setSlug} minWidth={200} options={projects.map(p => ({ value: p.slug, label: clean(p.name), badge: p.visibility === 'shared' ? 'shared' : undefined }))} />
      <span className="muted files-hint">Browse, edit &amp; preview project files</span>
    </div>
    <div className={`files-body ${path ? 'has-file' : ''}`} style={{ gridTemplateColumns: `${treeW}px 6px minmax(0, 1fr)` }}>
      {fs && <WorkspaceTree fs={fs} title="Files" className="files-tree" onOpenFile={setPath} activePath={path} />}
      <div className="files-resize" onMouseDown={startResize} role="separator" aria-label="Resize file tree" />
      <div className="files-main">
        {path && fs ? <FileView key={path} token={token} slug={slug} path={path} fs={fs} onClose={() => setPath(null)} />
          : <div className="files-empty"><p className="muted">Pilih file dari kiri buat lihat / edit. File HTML bisa di-Preview (render), Markdown juga.</p></div>}
      </div>
    </div>
  </section>
}
