import { useRef, useState, useEffect } from 'react'
import { faq } from '../data/faq'
import { matchFaq } from '../utils/matchFaq'
import { useQaHistory } from '../hooks/useQaHistory'

const SUGGESTIONS = ['un vs une', 'tu ou vous', 'septante nonante', 'à vs de']

export function AskModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [input, setInput] = useState('')
  const { history, addExchange, clearHistory } = useQaHistory()
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (open && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [open, history.length])

  if (!open) return null

  const submit = (text: string) => {
    const trimmed = text.trim()
    if (!trimmed) return
    const matches = matchFaq(trimmed)
    addExchange(trimmed, matches.map((m) => m.id))
    setInput('')
  }

  return (
    <div className="ask-backdrop" onClick={onClose}>
      <div className="ask-sheet" onClick={(e) => e.stopPropagation()}>
        <div className="ask-header">
          <div>
            <h2>Ask a question</h2>
            <p className="muted">No need to leave your exercise — just type it below.</p>
          </div>
          <button type="button" className="ask-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <div className="ask-conversation" ref={scrollRef}>
          {history.length === 0 && (
            <div className="ask-empty">
              <p>Stuck on something? Try asking things like:</p>
              <div className="ask-suggestions">
                {SUGGESTIONS.map((s) => (
                  <button key={s} type="button" onClick={() => submit(s)}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {history.map((exchange) => {
            const answers = exchange.answerIds
              .map((id) => faq.find((f) => f.id === id))
              .filter((f): f is NonNullable<typeof f> => Boolean(f))
            return (
              <div key={exchange.id} className="qa-exchange">
                <div className="qa-bubble qa-question">{exchange.question}</div>
                {answers.length > 0 ? (
                  answers.map((a) => (
                    <div key={a.id} className="qa-bubble qa-answer">
                      <p className="qa-answer-title">{a.question}</p>
                      <p>{a.answer}</p>
                    </div>
                  ))
                ) : (
                  <div className="qa-bubble qa-answer qa-no-match">
                    <p>
                      I don't have a specific answer for that yet. Try rephrasing, or ask
                      about one of these common mix-ups:
                    </p>
                    <div className="ask-suggestions">
                      {SUGGESTIONS.map((s) => (
                        <button key={s} type="button" onClick={() => submit(s)}>
                          {s}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        <form
          className="ask-input-row"
          onSubmit={(e) => {
            e.preventDefault()
            submit(input)
          }}
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder='e.g. "when do I use un vs une?"'
            autoComplete="off"
          />
          <button type="submit" disabled={!input.trim()}>
            Ask
          </button>
        </form>

        {history.length > 0 && (
          <button type="button" className="ask-clear" onClick={clearHistory}>
            Clear conversation
          </button>
        )}
      </div>
    </div>
  )
}
