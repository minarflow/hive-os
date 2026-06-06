import React from 'react'
import CodeMirror from '@uiw/react-codemirror'
import { markdown } from '@codemirror/lang-markdown'
import { oneDark } from '@codemirror/theme-one-dark'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { FsAdapter } from '../../api/fsAdapter'
import { baseName, linkifyWiki } from './wikiGraph'

export function WikiNote({ fs, path, backlinks, resolve, onOpenNote, onClose, onSaved }: {
  fs: FsAdapter
  path: string
  backlinks: string[]
  resolve: (name: string) => string | null
  onOpenNote: (path: string) => void
  onClose: () => void
  onSaved: () => void
}) {
  const [content, setContent] = React.useState('')
  const [dirty, setDirty] = React.useState(false)
  const [mode, setMode] = React.useState<'edit' | 'preview'>('preview')
  const [status, setStatus] = React.useState('loading')
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark'

  React.useEffect(() => {
    setStatus('loading'); setDirty(false)
    fs.read(path).then(b => { setContent(b.content); setStatus('ready') }).catch(e => setStatus(String(e)))
  }, [fs, path])

  const save = async () => {
    setStatus('saving')
    try { await fs.write(path, content); setDirty(false); setStatus('saved'); onSaved() } catch (e) { setStatus(String(e)) }
  }

  return <div className="wiki-note">
    <div className="wiki-note-head">
      <strong title={path}>{baseName(path)}{dirty ? ' •' : ''}</strong>
      <div className="seg sm"><button className={mode === 'edit' ? 'active' : ''} onClick={() => setMode('edit')}>Edit</button><button className={mode === 'preview' ? 'active' : ''} onClick={() => setMode('preview')}>Preview</button></div>
      <div><button className="ghost-button" onClick={() => void save()}>Save</button><button className="ghost-button" onClick={onClose}>Close</button></div>
    </div>
    {status === 'loading'
      ? <p className="muted" style={{ padding: 10 }}>Loading…</p>
      : mode === 'edit'
        ? <div className="cm-wrap"><CodeMirror value={content} height="100%" theme={isDark ? oneDark : 'light'} extensions={[markdown()]} onChange={v => { setContent(v); setDirty(true) }} basicSetup={{ lineNumbers: true, highlightActiveLine: true }} /></div>
        : <div className="wiki-preview md"><ReactMarkdown remarkPlugins={[remarkGfm]} components={{
            a: ({ href, children }) => {
              if (href && href.startsWith('#wiki:')) {
                const target = decodeURIComponent(href.slice(6))
                const tp = resolve(target)
                return <a className={`wikilink ${tp ? '' : 'missing'}`} href="#" onClick={e => { e.preventDefault(); if (tp) onOpenNote(tp) }}>{children}</a>
              }
              return <a href={href} target="_blank" rel="noreferrer">{children}</a>
            }
          }}>{linkifyWiki(content)}</ReactMarkdown></div>}
    <div className="wiki-backlinks">
      <p className="eyebrow">Linked mentions ({backlinks.length})</p>
      {backlinks.length === 0 ? <p className="muted">No backlinks yet.</p> : backlinks.map(b => <button key={b} className="backlink" onClick={() => onOpenNote(b)}>{baseName(b)}</button>)}
    </div>
    <div className="file-editor-status muted">{status === 'saved' ? 'Saved' : status === 'saving' ? 'Saving…' : dirty ? 'Unsaved · click Save' : 'Up to date'}</div>
  </div>
}
