import React from 'react'
import type { RunEvent } from '../types'

export function useEventStream(token: string, sessionId: number | null, onEvent: (event: RunEvent) => void) {
  const [connected, setConnected] = React.useState(false)
  const lastSeq = React.useRef(0)

  // Keep the latest handler in a ref so the EventSource is created ONCE per
  // (token, sessionId) instead of reconnecting on every render when `onEvent`
  // changes identity. Reconnecting each render made the stream flap, which
  // showed up as the connection dot flickering.
  const handlerRef = React.useRef(onEvent)
  React.useEffect(() => { handlerRef.current = onEvent }, [onEvent])

  React.useEffect(() => {
    lastSeq.current = 0
    if (!token || !sessionId) return
    let closed = false
    const emit = (data: string) => {
      if (closed) return
      const parsed = JSON.parse(data) as RunEvent
      lastSeq.current = Math.max(lastSeq.current, parsed.seq)
      handlerRef.current(parsed)
    }
    const source = new EventSource(`/api/sessions/${sessionId}/events/stream?after_seq=${lastSeq.current}&token=${encodeURIComponent(token)}`)
    source.onopen = () => setConnected(true)
    source.onerror = () => setConnected(false)
    source.onmessage = event => emit(event.data)
    const types = ['run.queued', 'run.started', 'message.delta', 'reasoning.delta', 'tool.start', 'tool.complete', 'message.complete', 'run.completed', 'run.failed', 'run.cancelled', 'warning']
    for (const type of types) {
      source.addEventListener(type, event => emit((event as MessageEvent).data))
    }
    return () => {
      closed = true
      source.close()
      setConnected(false)
    }
  }, [token, sessionId])

  return { connected }
}
