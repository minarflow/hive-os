import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { IconCopy, IconCheck } from '../shell/icons'

// A fenced code block with a copy button. The copy reads the rendered text
// straight off the <pre>, so it works regardless of language/highlighting.
function CodeBlock({ children }: { children?: React.ReactNode }) {
  const ref = React.useRef<HTMLPreElement>(null)
  const [copied, setCopied] = React.useState(false)
  const copy = async () => {
    const text = ref.current?.innerText ?? ''
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1400)
    } catch { /* clipboard unavailable */ }
  }
  return (
    <div className="code-block">
      <button className={`copy-btn ${copied ? 'copied' : ''}`} onClick={copy} title="Copy code" aria-label="Copy code">{copied ? <IconCheck size={14} /> : <IconCopy size={14} />}<span>{copied ? 'Copied' : 'Copy'}</span></button>
      <pre ref={ref}>{children}</pre>
    </div>
  )
}

// Renders assistant/streaming text as GitHub-flavored markdown. react-markdown
// tolerates partial markdown during streaming (an unclosed code fence renders
// progressively as a code block), so it is safe to feed in-flight deltas.
export function MessageContent({ content }: { content: string }) {
  return (
    <div className="md">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ pre: ({ children }) => <CodeBlock>{children}</CodeBlock> }}>
        {content}
      </ReactMarkdown>
    </div>
  )
}
