import type { Week } from '../data/curriculum'
import { useProgress } from '../hooks/useProgress'

export function ProgressScreen({ week }: { week: Week }) {
  const { isSessionComplete, completedSessionsCount, knownVocabCount } = useProgress()
  const totalSessions = week.sessions.length
  const weekDone = completedSessionsCount === totalSessions

  return (
    <div className="screen">
      <div className="hero-card">
        <p className="hero-eyebrow">Your progress</p>
        <p className="hero-goal">
          {weekDone
            ? "Week 1 checkpoint cleared. You're ready for Week 2."
            : 'Keep going — finish every session to unlock the Week 1 checkpoint.'}
        </p>
      </div>

      <section className="card">
        <h2>{week.title}</h2>
        <ul className="progress-session-list">
          {week.sessions.map((s) => (
            <li key={s.id} className="progress-session-row">
              <span className={`status-dot ${isSessionComplete(week.id, s.id) ? 'done' : ''}`} />
              <span>{s.title}</span>
              <span className="muted">{isSessionComplete(week.id, s.id) ? 'Done' : 'To do'}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="card stats-card">
        <div>
          <p className="stat-value">{completedSessionsCount}/{totalSessions}</p>
          <p className="stat-label">Sessions complete</p>
        </div>
        <div>
          <p className="stat-value">{knownVocabCount}/{week.vocab.length}</p>
          <p className="stat-label">Words known</p>
        </div>
      </section>
    </div>
  )
}
