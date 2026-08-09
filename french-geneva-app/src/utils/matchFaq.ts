import { faq, type FaqEntry } from '../data/faq'

function normalize(text: string) {
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(new RegExp('[\\u0300-\\u036f]', 'g'), '')
    .replace(/[^a-z0-9\s]/g, ' ')
}

const STOP_WORDS = new Set([
  'the', 'a', 'an', 'is', 'are', 'to', 'of', 'and', 'or', 'i', 'do', 'does',
  'when', 'what', 'why', 'how', 'use', 'used', 'for', 'in', 'on', 'it', 'me',
  'my', 'so', 'was', 'be', 'vs', 'versus', 'between', 'difference', 'just',
])

export function matchFaq(query: string): FaqEntry[] {
  const normalizedQuery = normalize(query)
  const queryWords = normalizedQuery.split(/\s+/).filter((w) => w.length >= 2)

  const scored = faq.map((entry) => {
    const haystack = normalize(
      `${entry.question} ${entry.answer} ${entry.keywords.join(' ')}`,
    )
    const keywordHaystack = entry.keywords.map((k) => normalize(k))

    let score = 0
    for (const word of queryWords) {
      // An exact match against a curated keyword always counts, even if the
      // word is also a common English stopword (e.g. "on" is both a French
      // grammar word we teach and an English preposition we'd otherwise skip).
      if (keywordHaystack.some((k) => k === word)) {
        score += 3
        continue
      }
      if (STOP_WORDS.has(word)) continue
      if (haystack.includes(word)) score += 1
    }
    // Bonus for exact multi-word keyword phrases appearing in the query
    for (const keyword of keywordHaystack) {
      if (keyword.includes(' ') && normalizedQuery.includes(keyword)) score += 4
    }
    return { entry, score }
  })

  return scored
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 3)
    .map((s) => s.entry)
}
