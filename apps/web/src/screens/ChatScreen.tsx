import React from 'react'
import { createRun, cancelRun, listEvents } from '../api/runs'
import { createSession, listMessages } from '../api/sessions'
import { useEventStream } from '../hooks/useEventStream'
import type { ChatMessage, ChatSession, Profile, Project, RunEvent } from '../types'
import { ChatThread } from '../components/chat/ChatThread'
import { Composer } from '../components/chat/Composer'
import { Dropdown } from '../components/ui/Dropdown'
import { notify } from '../lib/notify'

const cleanName = (n: string) => n.replace(/\s*\(private\)\s*$/i, '')

function localCommandReply(name: string, props: { activeProject: Project | null; activeProfile: Profile | null; activeSession: ChatSession | null }): string {
  switch (name) {
    case '/help': return 'Commands: /new (new session), /status, /session, /project, /runner. Prefix // to send a literal slash message to Hermes.'
    case '/status': return `Project: ${props.activeProject?.name || 'none'} · Profile: ${props.activeProfile?.name || 'none'} · Runner: hermes`
    case '/session': return `Session: ${props.activeSession?.title || 'new chat'}`
    case '/project': return `Project: ${props.activeProject?.name || 'none'} (${props.activeProject?.slug || '-'})`
    case '/runner': return 'Active runner: hermes (only runner enabled).'
    default: return 'Unknown command.'
  }
}

export function ChatScreen(props: { token: string; activeProfile: Profile | null; activeProject: Project | null; activeSession: ChatSession | null; profiles: Profile[]; projects: Project[]; onActiveProfile: (p: Profile) => void; onActiveProject: (p: Project | null) => void; onSession: (s: ChatSession) => void; onRefresh: () => Promise<void>; onNewSession: () => Promise<void> }) {
  const [messages, setMessages] = React.useState<ChatMessage[]>([])
  const [events, setEvents] = React.useState<RunEvent[]>([])
  const [busyRun, setBusyRun] = React.useState<number | null>(null)
  const [localSession, setLocalSession] = React.useState<ChatSession | null>(null)
  const [error, setError] = React.useState('')
  const activeSession = localSession || props.activeSession

  const loadMessages = React.useCallback(async (sessionId?: number) => {
    const id = sessionId || activeSession?.id
    if (!id) { setMessages([]); setEvents([]); return }
    const body = await listMessages(props.token, id)
    const eventBody = await listEvents(props.token, id)
    setMessages(body.messages); setEvents(eventBody.events)
  }, [activeSession?.id, props.token])

  // Coalesce high-frequency message.delta events and flush at ~30fps so the
  // markdown thread isn't re-parsed on every token. Control events flush now.
  const bufferRef = React.useRef<RunEvent[]>([])
  const timerRef = React.useRef<number | null>(null)
  const flush = React.useCallback(() => {
    timerRef.current = null
    const buf = bufferRef.current
    if (!buf.length) return
    bufferRef.current = []
    setEvents(current => {
      const seen = new Set(current.map(e => e.id))
      const add = buf.filter(e => !seen.has(e.id))
      return add.length ? [...current, ...add] : current
    })
  }, [])

  const onEvent = React.useCallback((event: RunEvent) => {
    bufferRef.current.push(event)
    if (event.type === 'message.delta') {
      if (timerRef.current == null) timerRef.current = window.setTimeout(flush, 33)
      return
    }
    if (timerRef.current != null) { clearTimeout(timerRef.current); timerRef.current = null }
    flush()
    if (['run.completed', 'run.failed', 'run.cancelled'].includes(event.type)) { setBusyRun(null); void loadMessages(event.session_id); window.dispatchEvent(new CustomEvent('hive:files-changed')); if (event.type === 'run.completed') notify('Hermes selesai', 'Ada balasan baru di chat.') }
    else if (event.type === 'message.complete') void loadMessages(event.session_id)
  }, [flush, loadMessages])

  React.useEffect(() => () => { if (timerRef.current != null) clearTimeout(timerRef.current) }, [])

  const { connected } = useEventStream(props.token, activeSession?.id || null, onEvent)

  React.useEffect(() => {
    setLocalSession(null)
    setBusyRun(null)
    void loadMessages(props.activeSession?.id).catch(err => setError(String(err)))
  }, [props.activeSession?.id, loadMessages])

  async function ensureSession(text: string): Promise<ChatSession> {
    if (activeSession) return activeSession
    const created = await createSession(props.token, { title: text.slice(0, 60), project_slug: props.activeProject?.slug || null, profile_id: props.activeProfile?.id || null })
    setLocalSession(created)
    props.onSession(created)
    return created
  }

  async function submit(text: string) {
    setError('')
    try {
      const trimmed = text.trim()
      if (trimmed.startsWith('/') && !trimmed.startsWith('//')) {
        const name = trimmed.split(/\s+/)[0].toLowerCase()
        if (name === '/new' || name === '/reset') { await props.onNewSession(); return }
        if (name === '/help' || name === '/status' || name === '/session' || name === '/project' || name === '/runner') {
          setMessages(current => [...current, { role: 'system', content: localCommandReply(name, props) }])
          return
        }
        if (name === '/model' || name === '/clear' || name === '/tools') {
          setMessages(current => [...current, { role: 'system', content: `${name} is managed by Hive OS UI, not raw chat.` }])
          return
        }
        setMessages(current => [...current, { role: 'system', content: `Unknown command ${name}. Type /help to see available commands.` }])
        return
      }
      const prompt = trimmed.startsWith('//') ? trimmed.slice(1) : trimmed
      const session = await ensureSession(prompt)
      setMessages(current => [...current, { role: 'user', content: prompt }])
      const run = await createRun(props.token, session.id, { message: prompt, profile_id: props.activeProfile?.id || null, model: props.activeProfile?.default_model || null })
      setBusyRun(run.run_id)
      const eventBody = await listEvents(props.token, session.id)
      setEvents(eventBody.events)
      await props.onRefresh()
    } catch (err) { setError(String(err)) }
  }

  const controls = <div className="chat-controls">
    <label className="toolbar-control"><span className="ctl-label">Projects</span>
      <Dropdown value={props.activeProject?.slug || ''} onChange={slug => { if (!slug) return props.onActiveProject(null); const p = props.projects.find(project => project.slug === slug); if (p) props.onActiveProject(p) }}
        options={[{ value: '', label: 'No project' }, ...props.projects.map(p => ({ value: p.slug, label: cleanName(p.name), badge: p.visibility === 'shared' ? 'shared' : undefined }))]} />
    </label>
    <span className="ctl-divider" />
    <label className="toolbar-control"><span className="ctl-label">Agents</span>
      <Dropdown value={String(props.activeProfile?.id || '')} onChange={id => { const p = props.profiles.find(profile => profile.id === Number(id)); if (p) props.onActiveProfile(p) }}
        options={props.profiles.map(p => ({ value: String(p.id), label: p.name }))} />
    </label>
    <span className="ctl-divider" />
    <span className={`stream-dot ${connected ? 'on' : ''}`} title={connected ? 'Stream connected' : 'Stream idle'} />{busyRun && <button className="ghost-button" onClick={() => void cancelRun(props.token, busyRun)} title="Cancel run">Cancel</button>}
  </div>
  return <section className="chat-stage"><ChatThread messages={messages} events={events} pendingRunId={busyRun} pendingText={busyRun ? 'Hermes is working…' : ''} />{error && <div className="error-bar">{error}</div>}<div className="chat-dock">{controls}<Composer disabled={!props.activeProfile} token={props.token} onSubmit={submit} /></div></section>
}
