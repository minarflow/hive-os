import React from 'react'
import { getCommandCatalog, type CatalogCommand } from '../../api/commands'
import { uploadFile } from '../../api/files'
import { IconPlus, IconClose, IconFile } from '../shell/icons'

const isImg = (n: string) => /\.(png|jpe?g|gif|webp|svg|bmp|avif)$/i.test(n)

type Att = { path: string; name: string; img: boolean }

export function Composer({ disabled, token, slug, onSubmit }: { disabled?: boolean; token: string; slug?: string; onSubmit: (text: string) => Promise<void> }) {
  const [draft, setDraft] = React.useState('')
  const [commands, setCommands] = React.useState<CatalogCommand[]>([])
  const [atts, setAtts] = React.useState<Att[]>([])
  const [uploading, setUploading] = React.useState(false)
  const taRef = React.useRef<HTMLTextAreaElement>(null)
  const fileRef = React.useRef<HTMLInputElement>(null)

  React.useEffect(() => {
    if (!token) return
    void getCommandCatalog(token).then(c => setCommands(c.groups.flatMap(g => g.commands))).catch(() => undefined)
  }, [token])

  React.useLayoutEffect(() => {
    const el = taRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }, [draft])

  async function handleFiles(list: FileList | File[] | null) {
    if (!slug || !list || list.length === 0) return
    setUploading(true)
    for (const f of Array.from(list)) {
      try { const r = await uploadFile(token, slug, f); setAtts(a => [...a, { path: r.path, name: r.name, img: isImg(r.name) }]) } catch { /* ignore */ }
    }
    setUploading(false)
    if (fileRef.current) fileRef.current.value = ''
  }

  const showPopover = draft.startsWith('/') && !draft.startsWith('//') && !draft.includes(' ')
  const matches = showPopover ? commands.filter(c => c.name.startsWith(draft.toLowerCase())) : []

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    const text = draft.trim()
    if ((!text && atts.length === 0) || disabled) return
    const refs = atts.map(a => a.img ? `![${a.name}](${a.path})` : `[${a.name}](${a.path})`)
    const content = [text, ...refs].filter(Boolean).join('\n\n')
    setDraft(''); setAtts([])
    await onSubmit(content)
  }

  return <form className="composer" onSubmit={submit} onDragOver={e => { if (slug) e.preventDefault() }} onDrop={e => { if (slug) { e.preventDefault(); void handleFiles(e.dataTransfer.files) } }}>
    {matches.length > 0 && <div className="slash-popover">{matches.map(c => <button type="button" key={c.name} onClick={() => setDraft(c.name + ' ')}><strong>{c.name}</strong><span>{c.description}</span><em>{c.surface}</em></button>)}</div>}
    {atts.length > 0 && <div className="composer-atts">{atts.map((a, i) => <span className="composer-att" key={i}><IconFile size={13} />{a.name}<button type="button" aria-label="Remove" onClick={() => setAtts(cur => cur.filter((_, j) => j !== i))}><IconClose size={12} /></button></span>)}</div>}
    <textarea ref={taRef} rows={1} placeholder="Message Hermes in this project…" value={draft}
      onChange={e => setDraft(e.target.value)}
      onPaste={e => { const files = [...e.clipboardData.items].filter(i => i.kind === 'file').map(i => i.getAsFile()).filter(Boolean) as File[]; if (files.length && slug) { e.preventDefault(); void handleFiles(files) } }}
      onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); e.currentTarget.form?.requestSubmit() } }} />
    <div className="composer-footer">
      <input ref={fileRef} type="file" multiple hidden onChange={e => void handleFiles(e.target.files)} />
      <button type="button" className="attach-btn" disabled={!slug || uploading} title={slug ? 'Attach files' : 'Pick a project to attach files'} onClick={() => fileRef.current?.click()}><IconPlus size={16} />{uploading ? 'Uploading…' : 'Attach'}</button>
      <button className="primary-button" disabled={disabled || (!draft.trim() && atts.length === 0)} type="submit">Send</button>
    </div>
  </form>
}
