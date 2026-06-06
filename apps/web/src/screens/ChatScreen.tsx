import React from 'react'
import { createRun, cancelRun, listEvents } from '../api/runs'
import { createSession, listMessages } from '../api/sessions'
import { useEventStream } from '../hooks/useEventStream'
import type { ChatMessage, ChatSession, Profile, Project, RunEvent } from '../types'
import { ChatThread } from '../components/chat/ChatThread'
import { Composer } from '../components/chat/Composer'

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

  const onEvent = React.useCallback((event: RunEvent) => {
    setEvents(current => current.some(e => e.id === event.id) ? current : [...current, event])
    if (['run.completed', 'run.failed', 'run.cancelled'].includes(event.type)) setBusyRun(null)
    if (event.type === 'message.complete') void loadMessages(event.session_id)
  }, [loadMessages])

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
      }
      const prompt = trimmed.startsWith('//') ? trimmed.slice(1) : text
      const session = await ensureSession(prompt)
      setMessages(current => [...current, { role: 'user', content: prompt }])
      const run = await createRun(props.token, session.id, { message: prompt, profile_id: props.activeProfile?.id || null, model: props.activeProfile?.default_model || null })
      setBusyRun(run.run_id)
      const eventBody = await listEvents(props.token, session.id)
      setEvents(eventBody.events)
      await props.onRefresh()
    } catch (err) { setError(String(err)) }
  }

  return <section className="chat-stage"><div className="toolbar-row"><label>Project<select value={props.activeProject?.slug || ''} onChange={e => { if (!e.target.value) return props.onActiveProject(null); const p = props.projects.find(project => project.slug === e.target.value); if (p) props.onActiveProject(p) }}><option value="">No project</option>{props.projects.map(project => <option key={project.slug} value={project.slug}>{project.name}</option>)}</select></label><label>Hermes profile<select value={props.activeProfile?.id || ''} onChange={e => { const p = props.profiles.find(profile => profile.id === Number(e.target.value)); if (p) props.onActiveProfile(p) }}>{props.profiles.map(profile => <option key={profile.id} value={profile.id}>{profile.name}</option>)}</select></label><span className={connected ? 'pill ready' : 'pill'}>{connected ? 'stream connected' : 'stream idle'}</span>{busyRun && <button onClick={() => void cancelRun(props.token, busyRun)}>Cancel run</button>}</div>{error && <div className="error-bar">{error}</div>}<ChatThread messages={messages} events={events} pendingRunId={busyRun} pendingText={busyRun ? 'Hermes is working…' : ''} /><Composer disabled={!props.activeProfile} token={props.token} onSubmit={submit} /></section>
}
