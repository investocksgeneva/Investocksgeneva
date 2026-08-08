import type { Week } from '../data/curriculum'
import { useProgress } from '../hooks/useProgress'

export function HomeScreen({
  week,
  onOpenSession,
}: {
  week: Week
  onOpenSession: (sessionId: number) => void
}) {
  const { isSessionComplete, completedSessionsCount } = useProgress()
  const total = week.sessions.length

  return (
    <div className="screen">
      <div className="hero-card">
        <p className="hero-eyebrow">{week.title}</p>
        <p className="hero-goal">{week.goal}</p>
        <div className="hero-progress">
          <div className="progress-bar">
            <div
              className="progress-bar-fill"
              style={{ width: `${(completedSessionsCount / total) * 100}%` }}
            />
          </div>
          <span>
            {completedSessionsCount}/{total} sessions
          </span>
        </div>
      </div>

      <ul className="session-list">
        {week.sessions.map((session) => {
          const done = isSessionComplete(week.id, session.id)
          return (
            <li key={session.id}>
              <button
                type="button"
                className={`session-card ${done ? 'done' : ''}`}
                onClick={() => onOpenSession(session.id)}
              >
                <span className="session-number">{done ? '✓' : session.id}</span>
                <span className="session-text">
                  <span className="session-title">{session.title}</span>
                  <span className="session-subtitle">{session.subtitle}</span>
                </span>
                <span className="chevron">›</span>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
