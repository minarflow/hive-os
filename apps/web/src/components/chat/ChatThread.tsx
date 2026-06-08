import React from 'react'
import type { ChatMessage, RunEvent } from '../../types'
import { MessageContent } from './MessageContent'
import { IconSparkle, IconArrowDown } from '../shell/icons'

const ROLE_LABEL: Record<string, string> = { user: 'You', assistant: 'Agent', error: 'Run error', system: 'Hive OS' }

export function ChatThread({ messages, events, pendingRunId, token, slug, agentName }: { messages: ChatMessage[]; events: RunEvent[]; pendingRunId?: number | null; pendingText?: string; token?: string; slug?: string; agentName?: string }) {
  // Label = recorded author (username for people, profile/agent name for the
  // agent); falls back to the live agent name or the generic role label.
  const labelFor = (m: ChatMessage) => m.author || (m.role === 'assistant' ? (agentName || 'Agent') : (ROLE_LABEL[m.role] || 'Hive OS'))
  const agentLabel = agentName || 'Agent'
  // The live streaming bubble shows while a run is pending. The owner clears
  // pendingRunId only AFTER reloading the stored message, so the live text never
  // double-renders with (or vanishes before) the saved message (anti-flicker).
  const live = !!pendingRunId
  const streaming = live ? events.filter(e => e.type === 'message.delta' && e.run_id === pendingRunId).map(e => String(e.payload.text || '')).join('') : ''
  const waiting = live && !streaming

  // Compact tool-activity cards for the live run (from ACP tool.start/tool.complete).
  const tools: { id: string; title: string; status: string }[] = []
  if (live) {
    const byId = new Map<string, { id: string; title: string; status: string }>()
    for (const e of events) {
      if (e.run_id !== pendingRunId) continue
      if (e.type === 'tool.start') {
        const id = String(e.payload.id ?? e.id)
        byId.set(id, { id, title: String(e.payload.title || 'tool'), status: 'running' })
      } else if (e.type === 'tool.complete') {
        const id = String(e.payload.id ?? '')
        const card = byId.get(id)
        if (card) card.status = String(e.payload.status || 'completed')
      }
    }
    tools.push(...byId.values())
  }

  const scrollRef = React.useRef<HTMLDivElement>(null)
  const pinnedRef = React.useRef(true)
  const [atBottom, setAtBottom] = React.useState(true)

  const onScroll = () => {
    const el = scrollRef.current
    if (!el) return
    const pinned = el.scrollHeight - el.scrollTop - el.clientHeight < 80
    pinnedRef.current = pinned
    setAtBottom(pinned)
  }

  // Follow new content only when the user is already near the bottom.
  React.useLayoutEffect(() => {
    if (pinnedRef.current && scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [messages, streaming, waiting, tools.length])

  const scrollToBottom = () => {
    const el = scrollRef.current
    if (el) { el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' }); pinnedRef.current = true; setAtBottom(true) }
  }

  const empty = messages.length === 0 && !live

  return <div className="thread" ref={scrollRef} onScroll={onScroll}>
    <div className="chat-log">
      {empty && <div className="chat-empty"><div className="chat-empty-mark"><IconSparkle size={30} /></div><h3>Start a conversation</h3><p>Ask your agent anything in this project. Type <code>/</code> for commands.</p></div>}
      {messages.map((message, index) => <div className={`chat-line ${message.role} enter`} key={message.id ?? index}><strong>{labelFor(message)}</strong><MessageContent content={message.content} token={token} slug={slug} /></div>)}
      {tools.length > 0 && <div className="tool-cards enter">{tools.map(t => <div key={t.id} className={`tool-card ${t.status}`}><span className="tool-dot" />{t.title}</div>)}</div>}
      {streaming && <div className="chat-line assistant"><strong>{agentLabel}</strong><span className="md-stream">{streaming}</span></div>}
      {waiting && <div className="chat-line pending enter"><strong>{agentLabel}</strong><span className="typing"><i /><i /><i /></span></div>}
    </div>
    {!atBottom && <button className="scroll-bottom" onClick={scrollToBottom} aria-label="Scroll to latest" title="Scroll to latest"><IconArrowDown size={18} /></button>}
  </div>
}
