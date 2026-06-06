import React from 'react'
import { readFile, writeFile } from '../../api/files'

export function FileEditor({ token, slug, path, onClose }: { token: string; slug: string; path: string; onClose: () => void }) {
  const [content, setContent] = React.useState('')
  const [status, setStatus] = React.useState('loading')

  React.useEffect(() => {
    setStatus('loading')
    readFile(token, slug, path).then(b => { setContent(b.content); setStatus('ready') }).catch(e => setStatus(String(e)))
  }, [token, slug, path])

  async function save() {
    setStatus('saving')
    try { await writeFile(token, slug, path, content); setStatus('saved') } catch (e) { setStatus(String(e)) }
  }

  return <div className="file-editor">
    <div className="file-editor-head"><strong>{path}</strong><div><button onClick={() => void save()}>Save</button><button onClick={onClose}>Close</button></div></div>
    {status === 'loading' ? <p className="muted">Loading…</p> : <textarea value={content} onChange={e => setContent(e.target.value)} />}
    <div className="file-editor-status muted">{status}</div>
  </div>
}
