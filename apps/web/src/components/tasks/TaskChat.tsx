import React from 'react'
import { createRun, cancelRun, listEvents } from '../../api/runs'
import { listMessages } from '../../api/sessions'
import { useEventStream } from '../../hooks/useEventStream'
import type { ChatMessage, RunEvent } from '../../types'
import { ChatThread } from '../chat/ChatThread'
import { Composer } from '../chat/Composer'

// A focused agent thread bound to one session (the task's thread). Reuses the
// same streaming + tool-card rendering as the main chat.
export function TaskChat({ token, sessionId }: { token: string; sessionId: number }) {
  const [messages, setMessages] = React.useState<ChatMessage[]>([])
  const [events, setEvents] = React.useState<RunEvent[]>([])
  const [busyRun, setBusyRun] = React.useState<number | null>(null)
  const [error, setError] = React.useState('')

  const load = React.useCallback(async () => {
    const m = await listMessages(token, sessionId)
    const e = await listEvents(token, sessionId)
    setMessages(m.messages); setEvents(e.events)
  }, [token, sessionId])

  const bufferRef = React.useRef<RunEvent[]>([])
  const timerRef = React.useRef<number | null>(null)
  const flush = React.useCallback(() => {
    timerRef.current = null
    const buf = bufferRef.current
    if (!buf.length) return
    bufferRef.current = []
    setEvents(cur => { const seen = new Set(cur.map(e => e.id)); const add = buf.filter(e => !seen.has(e.id)); return add.length ? [...cur, ...add] : cur })
  }, [])

  const onEvent = React.useCallback((event: RunEvent) => {
    bufferRef.current.push(event)
    if (event.type === 'message.delta') { if (timerRef.current == null) timerRef.current = window.setTimeout(flush, 33); return }
    if (timerRef.current != null) { clearTimeout(timerRef.current); timerRef.current = null }
    flush()
    if (['run.completed', 'run.failed', 'run.cancelled'].includes(event.type)) { setBusyRun(null); void load(); window.dispatchEvent(new CustomEvent('hive:files-changed')) }
    else if (event.type === 'message.complete') void load()
  }, [flush, load])

  React.useEffect(() => () => { if (timerRef.current != null) clearTimeout(timerRef.current) }, [])
  const { connected } = useEventStream(token, sessionId, onEvent)
  React.useEffect(() => { setBusyRun(null); void load().catch(e => setError(String(e))) }, [load])

  async function submit(text: string) {
    const prompt = text.trim().startsWith('//') ? text.trim().slice(1) : text.trim()
    if (!prompt) return
    setError('')
    try {
      setMessages(cur => [...cur, { role: 'user', content: prompt }])
      const run = await createRun(token, sessionId, { message: prompt, profile_id: null, model: null })
      setBusyRun(run.run_id)
      setEvents((await listEvents(token, sessionId)).events)
    } catch (e) { setError(String(e)) }
  }

  return <div className="task-chat">
    <ChatThread messages={messages} events={events} pendingRunId={busyRun} />
    {error && <div className="error-bar">{error}</div>}
    <div className="chat-dock"><div className="chat-controls"><span className={`stream-dot ${connected ? 'on' : ''}`} title={connected ? 'Stream connected' : 'Stream idle'} />{busyRun && <button className="ghost-button" onClick={() => void cancelRun(token, busyRun)}>Stop</button>}</div><Composer disabled={false} token={token} onSubmit={submit} /></div>
  </div>
}
