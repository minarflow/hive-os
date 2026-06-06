import type { ChatMessage, RunEvent } from '../../types'

export function ChatThread({ messages, events, pendingRunId, pendingText }: { messages: ChatMessage[]; events: RunEvent[]; pendingRunId?: number | null; pendingText?: string }) {
  const completedRunIds = new Set(events.filter(e => ['message.complete', 'run.completed', 'run.failed', 'run.cancelled'].includes(e.type)).map(e => e.run_id))
  const deltas = pendingRunId && !completedRunIds.has(pendingRunId)
    ? events.filter(e => e.type === 'message.delta' && e.run_id === pendingRunId).map(e => String(e.payload.text || '')).join('')
    : ''
  const failures = events.filter(e => e.type === 'run.failed')

  return <div className="thread"><div className="chat-log">
    {messages.map((message, index) => <div className={`chat-line ${message.role}`} key={message.id ?? index}><strong>{message.role === 'user' ? 'You' : message.role === 'assistant' ? 'Hermes' : 'Hive OS'}</strong><span>{message.content}</span></div>)}
    {deltas && <div className="chat-line assistant"><strong>Hermes streaming</strong><span>{deltas}</span></div>}
    {failures.map(e => <div className="chat-line error" key={`err-${e.id}`}><strong>Run error</strong><span>{String(e.payload.error || 'Run failed')}</span></div>)}
    {pendingText && <div className="chat-line pending"><strong>Run</strong><span><i className="typing-dot" /> {pendingText}</span></div>}
  </div></div>
}
