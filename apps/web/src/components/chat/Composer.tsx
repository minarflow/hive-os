import React from 'react'
import { getCommandCatalog, type CatalogCommand } from '../../api/commands'

export function Composer({ disabled, token, onSubmit }: { disabled?: boolean; token: string; onSubmit: (text: string) => Promise<void> }) {
  const [draft, setDraft] = React.useState('')
  const [commands, setCommands] = React.useState<CatalogCommand[]>([])
  const taRef = React.useRef<HTMLTextAreaElement>(null)

  React.useEffect(() => {
    if (!token) return
    void getCommandCatalog(token).then(c => setCommands(c.groups.flatMap(g => g.commands))).catch(() => undefined)
  }, [token])

  // Auto-grow the textarea with content, capped so it never eats the thread.
  React.useLayoutEffect(() => {
    const el = taRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }, [draft])

  const showPopover = draft.startsWith('/') && !draft.startsWith('//') && !draft.includes(' ')
  const matches = showPopover ? commands.filter(c => c.name.startsWith(draft.toLowerCase())) : []

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    const text = draft.trim()
    if (!text || disabled) return
    setDraft('')
    await onSubmit(text)
  }

  return <form className="composer" onSubmit={submit}>
    {matches.length > 0 && <div className="slash-popover">{matches.map(c => <button type="button" key={c.name} onClick={() => setDraft(c.name + ' ')}><strong>{c.name}</strong><span>{c.description}</span><em>{c.surface}</em></button>)}</div>}
    <textarea ref={taRef} rows={1} placeholder="Message Hermes in this project…" value={draft} onChange={e => setDraft(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); e.currentTarget.form?.requestSubmit() } }} />
    <div className="composer-footer end"><button className="primary-button" disabled={disabled || !draft.trim()} type="submit">Send</button></div>
  </form>
}
