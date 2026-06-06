import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// Renders assistant/streaming text as GitHub-flavored markdown. react-markdown
// tolerates partial markdown during streaming (an unclosed code fence renders
// progressively as a code block), so it is safe to feed in-flight deltas.
export function MessageContent({ content }: { content: string }) {
  return (
    <div className="md">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  )
}
