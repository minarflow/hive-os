import React from 'react'
import { createRun, cancelRun, listEvents } from '../api/runs'
import { createSession, listMessages } from '../api/sessions'
import { draftWikiNote, commitWikiNote } from '../api/wiki'
import { useEventStream } from '../hooks/useEventStream'
import type { ChatMessage, ChatSession, Profile, Project, RunEvent, WikiDraft } from '../types'
import { ChatThread } from '../components/chat/ChatThread'
import { WikiNotePreview } from '../components/wiki/WikiNotePreview'
import { Composer } from '../components/chat/Composer'
import { Dropdown } from '../components/ui/Dropdown'
import { IconProjects, IconAgents, IconWiki } from '../components/shell/icons'
import { notify } from '../lib/notify'

const cleanName = (n: string) => n.replace(/\s*\(private\)\s*$/i, '')

function localCommandReply(name: string, props: { activeProject: Project | null; activeProfile: Profile | null; activeSession: ChatSession | null }): string {
  switch (name) {
    case '/help': return 'Commands: /new (new session), /status, /session, /project [name|none] (move this chat into/out of a project), /runner. Prefix // to send a literal slash message to Hermes.'
    case '/status': return `Project: ${props.activeProject?.name || 'none'} · Profile: ${props.activeProfile?.name || 'none'} · Runner: hermes`
    case '/session': return `Session: ${props.activeSession?.title || 'new chat'}`
    case '/project': return `Project: ${props.activeProject?.name || 'none'} (${props.activeProject?.slug || '-'}). Type "/project <name>" to switch to another project's chat.`
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
  const [wikiDraft, setWikiDraft] = React.useState<WikiDraft | null>(null)
  const [savingWiki, setSavingWiki] = React.useState(false)
  const seenDraftSeq = React.useRef(0)
  const activeSession = localSession || props.activeSession

  // Open the preview when a wiki.draft event arrives on this session's stream.
  React.useEffect(() => {
    const ev = [...events].reverse().find(e => e.type === 'wiki.draft' && e.seq > seenDraftSeq.current)
    if (ev) { seenDraftSeq.current = ev.seq; setWikiDraft(ev.payload as unknown as WikiDraft); setSavingWiki(false) }
  }, [events])

  async function startWikiDraft() {
    if (!activeSession) return
    setSavingWiki(true); setError('')
    try { await draftWikiNote(props.token, activeSession.id, props.activeProfile?.id) }
    catch (e) { setSavingWiki(false); setError(String(e)) }
  }

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
    if (['run.completed', 'run.failed', 'run.cancelled'].includes(event.type)) { void loadMessages(event.session_id).then(() => setBusyRun(null)); window.dispatchEvent(new CustomEvent('hive:files-changed')); if (event.type === 'run.completed') notify('Hermes finished', 'New reply in chat.') }
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

  // Switch to a project: the parent opens that project's most recent chat (or a
  // blank new one). Each project keeps its own conversation history.
  function chooseProject(slug: string) {
    const p = props.projects.find(project => project.slug === slug) || null
    if (p) props.onActiveProject(p)
  }

  async function submit(text: string) {
    setError('')
    try {
      const trimmed = text.trim()
      if (trimmed.startsWith('/') && !trimmed.startsWith('//')) {
        const name = trimmed.split(/\s+/)[0].toLowerCase()
        if (name === '/new' || name === '/reset') { await props.onNewSession(); return }
        if (name === '/project') {
          const arg = trimmed.split(/\s+/).slice(1).join(' ').trim()
          if (arg) {
            const target = props.projects.find(p => p.slug === arg || cleanName(p.name).toLowerCase() === arg.toLowerCase())
            if (!target) { setMessages(current => [...current, { role: 'system', content: `No project matches "${arg}". Use the project name or slug.` }]); return }
            chooseProject(target.slug)
            return
          }
        }
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
    <label className="toolbar-control"><span className="ctl-icon" title="Project"><IconProjects size={15} /></span><span className="ctl-label">Projects</span>
      <Dropdown dropUp value={props.activeProject?.slug || ''} onChange={slug => chooseProject(slug)}
        options={props.projects.map(p => ({ value: p.slug, label: cleanName(p.name), badge: p.visibility === 'shared' ? 'shared' : undefined }))} />
    </label>
    <span className="ctl-divider" />
    <label className="toolbar-control"><span className="ctl-icon" title="Agent"><IconAgents size={15} /></span><span className="ctl-label">Agents</span>
      <Dropdown dropUp value={String(props.activeProfile?.id || '')} onChange={id => { const p = props.profiles.find(profile => profile.id === Number(id)); if (p) props.onActiveProfile(p) }}
        options={props.profiles.map(p => ({ value: String(p.id), label: p.name }))} />
    </label>
    <span className="ctl-divider" />
    <span className={`stream-dot ${connected ? 'on' : ''}`} title={connected ? 'Stream connected' : 'Stream idle'} />{busyRun && <button className="ghost-button" onClick={() => void cancelRun(props.token, busyRun)} title="Cancel run">Cancel</button>}
    {(activeSession?.project_slug || props.activeProject?.slug) && <>
      <span className="ctl-divider" />
      <button className="ghost-button icon-text" onClick={() => void startWikiDraft()} disabled={!activeSession || savingWiki} title="Distill this conversation into a wiki note"><IconWiki size={15} />{savingWiki ? 'Preparing…' : 'Save to wiki'}</button>
    </>}
  </div>
  const projSlug = activeSession?.project_slug || props.activeProject?.slug || undefined
  return <section className="chat-stage"><ChatThread messages={messages} events={events} pendingRunId={busyRun} pendingText={busyRun ? 'Working…' : ''} token={props.token} slug={projSlug} agentName={activeSession?.profile_name || props.activeProfile?.name || undefined} />{error && <div className="error-bar">{error}</div>}<div className="chat-dock">{controls}<Composer disabled={!props.activeProfile} token={props.token} slug={projSlug} onSubmit={submit} /></div>
    {wikiDraft && <WikiNotePreview
      draft={wikiDraft}
      onCancel={() => setWikiDraft(null)}
      onSave={async (path, content, mode) => {
        if (!activeSession) return
        await commitWikiNote(props.token, activeSession.id, path, content, mode)
        setWikiDraft(null)
        notify('Saved to wiki', path)
      }} />}
  </section>
}
