import React from 'react'
import type { RunEvent } from '../types'

export function useEventStream(token: string, sessionId: number | null, onEvent: (event: RunEvent) => void) {
  const [connected, setConnected] = React.useState(false)
  const lastSeq = React.useRef(0)

  React.useEffect(() => {
    lastSeq.current = 0
    if (!token || !sessionId) return
    let closed = false
    const source = new EventSource(`/api/sessions/${sessionId}/events/stream?after_seq=${lastSeq.current}&token=${encodeURIComponent(token)}`)
    source.onopen = () => setConnected(true)
    source.onerror = () => setConnected(false)
    source.onmessage = event => {
      if (closed) return
      const parsed = JSON.parse(event.data) as RunEvent
      lastSeq.current = Math.max(lastSeq.current, parsed.seq)
      onEvent(parsed)
    }
    const types = ['run.queued', 'run.started', 'message.delta', 'reasoning.delta', 'tool.start', 'tool.complete', 'message.complete', 'run.completed', 'run.failed', 'run.cancelled', 'warning']
    for (const type of types) {
      source.addEventListener(type, event => {
        if (closed) return
        const parsed = JSON.parse((event as MessageEvent).data) as RunEvent
        lastSeq.current = Math.max(lastSeq.current, parsed.seq)
        onEvent(parsed)
      })
    }
    return () => {
      closed = true
      source.close()
      setConnected(false)
    }
  }, [token, sessionId, onEvent])

  return { connected }
}
