import { useState } from 'react'
import type { Session } from '../data/curriculum'
import { SpeakButton } from '../components/SpeakButton'
import { DialogueView } from '../components/DialogueView'
import { useProgress } from '../hooks/useProgress'

export function SessionScreen({
  weekId,
  session,
}: {
  weekId: number
  session: Session
}) {
  const { isSessionComplete, setSessionComplete } = useProgress()
  const done = isSessionComplete(weekId, session.id)
  const [checkedSteps, setCheckedSteps] = useState<Record<number, boolean>>({})

  const allStepsChecked =
    session.roleplaySteps && session.roleplaySteps.length > 0
      ? session.roleplaySteps.every((_, i) => checkedSteps[i])
      : false

  return (
    <div className="screen">
      <p className="session-subtitle-label">{session.subtitle}</p>

      {session.corePhrases && (
        <section className="card">
          <h2>Core phrases</h2>
          <ul className="phrase-list">
            {session.corePhrases.map((p) => (
              <li key={p.fr} className="phrase-row">
                <div>
                  <p className="phrase-fr">{p.fr}</p>
                  <p className="phrase-en">{p.en}</p>
                </div>
                <SpeakButton text={p.fr} />
              </li>
            ))}
          </ul>
        </section>
      )}

      {session.grammarSeed && (
        <section className="card callout">
          <h2>Grammar seed</h2>
          <p>{session.grammarSeed}</p>
        </section>
      )}

      {session.numbers && (
        <section className="card">
          <h2>Numbers</h2>
          {session.numbersUseCase && <p className="muted">{session.numbersUseCase}</p>}
          <ul className="number-grid">
            {session.numbers.map((num) => (
              <li key={num.n} className={`number-chip ${num.swissTwist ? 'twist' : ''}`}>
                <div className="number-row">
                  <span className="number-digit">{num.n}</span>
                  <span className="number-fr">{num.fr}</span>
                  <SpeakButton text={num.fr} />
                </div>
                {num.swissTwist && (
                  <p className="swiss-twist-note">
                    <span className="badge">Swiss twist</span> {num.swissTwist}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {session.useCases && (
        <section className="card">
          <h2>Key phrases</h2>
          <ul className="phrase-list">
            {session.useCases.map((u) => (
              <li key={u.phrase} className="phrase-row">
                <div>
                  <p className="phrase-fr">{u.phrase}</p>
                  <p className="phrase-en">{u.use}</p>
                </div>
                <SpeakButton text={u.phrase} />
              </li>
            ))}
          </ul>
        </section>
      )}

      {session.dialogue && (
        <section className="card">
          <h2>Mini-dialogue</h2>
          <DialogueView lines={session.dialogue} />
        </section>
      )}

      {session.roleplaySteps && (
        <section className="card">
          <h2>Role-play checkpoint</h2>
          <p className="muted">
            Enter a shop, greet, ask for an item + price, pay, thank, leave — do it
            unscripted, then check off each step you managed live.
          </p>
          <ul className="checklist">
            {session.roleplaySteps.map((step, i) => (
              <li key={step.title}>
                <label className="checklist-item">
                  <input
                    type="checkbox"
                    checked={Boolean(checkedSteps[i])}
                    onChange={(e) =>
                      setCheckedSteps((prev) => ({ ...prev, [i]: e.target.checked }))
                    }
                  />
                  <span>
                    <span className="checklist-title">{step.title}</span>
                    <span className="checklist-hint">{step.hint}</span>
                  </span>
                  <SpeakButton text={step.hint} />
                </label>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="card drill-card">
        <h2>Drill</h2>
        <p>{session.drill}</p>
      </section>

      <button
        type="button"
        className={`complete-btn ${done ? 'done' : ''}`}
        disabled={Boolean(session.roleplaySteps) && !allStepsChecked && !done}
        onClick={() => setSessionComplete(weekId, session.id, !done)}
      >
        {done ? '✓ Session complete' : 'Mark session complete'}
      </button>
    </div>
  )
}
