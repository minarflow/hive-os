// Parse a set of wiki notes into a link graph (Obsidian-style [[wikilinks]]).
export type RawNote = { path: string; content: string }
export type GraphNode = { id: string; name: string; degree: number }
export type GraphLink = { source: string; target: string }
export type WikiModel = {
  notes: RawNote[]
  nodes: GraphNode[]
  links: GraphLink[]
  backlinks: Record<string, string[]>   // note path -> paths that link to it
  resolve: (name: string) => string | null
}

export const baseName = (p: string) => (p.split('/').pop() || p).replace(/\.md$/i, '')

const LINK_RE = /\[\[([^\]]+)\]\]/g

export function buildWikiModel(notes: RawNote[]): WikiModel {
  const byBase = new Map<string, string>()
  const byPath = new Map<string, string>()
  for (const n of notes) {
    byBase.set(baseName(n.path).toLowerCase(), n.path)
    byPath.set(n.path.toLowerCase(), n.path)
    byPath.set(n.path.toLowerCase().replace(/\.md$/i, ''), n.path)
  }
  const resolve = (name: string): string | null => {
    const t = name.trim().toLowerCase()
    return byPath.get(t) || byPath.get(t + '.md') || byBase.get(t) || byBase.get((t.split('/').pop() || t)) || null
  }

  const links: GraphLink[] = []
  const backlinks: Record<string, string[]> = {}
  const degree = new Map<string, number>()
  const bump = (p: string) => degree.set(p, (degree.get(p) || 0) + 1)
  const seen = new Set<string>()
  for (const n of notes) {
    let m: RegExpExecArray | null
    LINK_RE.lastIndex = 0
    while ((m = LINK_RE.exec(n.content))) {
      const target = m[1].split('|')[0].split('#')[0].trim()
      const tp = resolve(target)
      if (!tp || tp === n.path) continue
      const key = n.path + '->' + tp
      if (seen.has(key)) continue
      seen.add(key)
      links.push({ source: n.path, target: tp })
      ;(backlinks[tp] ||= []).push(n.path)
      bump(n.path); bump(tp)
    }
  }
  const nodes: GraphNode[] = notes.map(n => ({ id: n.path, name: baseName(n.path), degree: degree.get(n.path) || 0 }))
  return { notes, nodes, links, backlinks, resolve }
}

// Convert [[Target|alias]] into a markdown link (#wiki:Target) for preview.
export function linkifyWiki(content: string): string {
  return content.replace(LINK_RE, (_full, inner: string) => {
    const [target, alias] = inner.split('|')
    const label = (alias ?? target).trim()
    return `[${label}](#wiki:${encodeURIComponent(target.split('#')[0].trim())})`
  })
}
