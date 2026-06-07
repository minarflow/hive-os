import React from 'react'
import type { Project } from '../types'
import { WorkspaceTree } from '../components/files/WorkspaceTree'
import { projectFs } from '../api/fsAdapter'
import { fetchRawBlob } from '../api/files'
import { MessageContent } from '../components/chat/MessageContent'
import { Dropdown } from '../components/ui/Dropdown'

const IMG = /\.(png|jpe?g|gif|webp|svg|bmp|ico|avif)$/i
const clean = (n: string) => n.replace(/\s*\(private\)\s*$/i, '')

function ArtifactView({ token, slug, path, onClose }: { token: string; slug: string; path: string; onClose: () => void }) {
  const fs = React.useMemo(() => projectFs(token, slug, 'artifacts'), [token, slug])
  const [img, setImg] = React.useState<string | null>(null)
  const [text, setText] = React.useState<string | null>(null)
  const [status, setStatus] = React.useState('loading')

  React.useEffect(() => {
    let url: string | null = null
    setImg(null); setText(null); setStatus('loading')
    if (IMG.test(path)) {
      fetchRawBlob(token, slug, `artifacts/${path}`).then(u => { url = u; setImg(u); setStatus('ready') }).catch(e => setStatus(String(e)))
    } else {
      fs.read(path).then(b => { setText(b.content); setStatus('ready') }).catch(() => setStatus('binary'))
    }
    return () => { if (url) URL.revokeObjectURL(url) }
  }, [token, slug, path, fs])

  async function download() {
    try {
      const u = await fetchRawBlob(token, slug, `artifacts/${path}`)
      const a = document.createElement('a'); a.href = u; a.download = path.split('/').pop() || 'file'
      document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(u)
    } catch { /* */ }
  }

  return <div className="artifact-view">
    <div className="artifact-toolbar"><strong title={path}>{path.split('/').pop()}</strong><div><button className="ghost-button" onClick={() => void download()}>Download</button><button className="ghost-button" onClick={onClose}>Close</button></div></div>
    <div className="artifact-body">
      {status === 'loading' && <p className="muted" style={{ padding: 16 }}>Loading…</p>}
      {img && <div className="artifact-img"><img src={img} alt={path} /></div>}
      {text != null && (/\.(md|markdown)$/i.test(path) ? <div className="md" style={{ padding: 18 }}><MessageContent content={text} /></div> : <pre className="artifact-text">{text}</pre>)}
      {status === 'binary' && <p className="muted" style={{ padding: 16 }}>Preview not available for this file type. Use Download.</p>}
    </div>
  </div>
}

export function ArtifactsScreen({ token, projects, activeProject }: { token: string; projects: Project[]; activeProject: Project | null }) {
  const [slug, setSlug] = React.useState(activeProject?.slug || projects[0]?.slug || '')
  const [open, setOpen] = React.useState<string | null>(null)
  const project = projects.find(p => p.slug === slug) || null
  const fs = React.useMemo(() => (project ? projectFs(token, project.slug, 'artifacts') : null), [token, project?.slug])

  React.useEffect(() => { setOpen(null) }, [slug])

  if (projects.length === 0) return <section className="placeholder-view"><div className="assistant-bubble compact"><h1>Artifacts</h1><p>No projects yet.</p></div></section>

  return <section className="wiki-view">
    <div className="wiki-switch">
      <Dropdown value={slug} onChange={setSlug} minWidth={200} options={projects.map(p => ({ value: p.slug, label: clean(p.name), badge: p.visibility === 'shared' ? 'shared' : undefined }))} />
      <span className="wiki-hint">Files in <code>artifacts/</code></span>
    </div>
    <div className="wiki-files">
      {fs && <WorkspaceTree key={slug} fs={fs} title="Artifacts" className="wiki-tree" onOpenFile={setOpen} activePath={open} />}
      <div className="wiki-main">
        {open && project ? <ArtifactView token={token} slug={project.slug} path={open} onClose={() => setOpen(null)} />
          : <div className="wiki-placeholder"><p className="muted">Select an artifact to preview or download.</p></div>}
      </div>
    </div>
  </section>
}
