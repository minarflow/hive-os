import React from 'react'

export function Composer({ disabled, onSubmit }: { disabled?: boolean; onSubmit: (text: string) => Promise<void> }) {
  const [draft, setDraft] = React.useState('')
  async function submit(event: React.FormEvent) {
    event.preventDefault()
    const text = draft.trim()
    if (!text || disabled) return
    setDraft('')
    await onSubmit(text)
  }
  return <form className="composer" onSubmit={submit}><textarea placeholder="Message Hermes in this project…" value={draft} onChange={e => setDraft(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); e.currentTarget.form?.requestSubmit() } }} /><div className="composer-footer"><span>Hermes Team Mode · async streaming</span><button className="primary-button" disabled={disabled || !draft.trim()} type="submit">Send</button></div></form>
}
