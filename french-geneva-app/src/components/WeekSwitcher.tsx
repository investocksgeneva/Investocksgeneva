import type { Week } from '../data/curriculum'

export function WeekSwitcher({
  weeks,
  activeWeekId,
  onChange,
}: {
  weeks: Week[]
  activeWeekId: number
  onChange: (weekId: number) => void
}) {
  if (weeks.length < 2) return null
  return (
    <div className="week-switcher">
      {weeks.map((week) => (
        <button
          key={week.id}
          type="button"
          className={`week-switcher-item ${week.id === activeWeekId ? 'active' : ''}`}
          onClick={() => onChange(week.id)}
        >
          Week {week.id}
        </button>
      ))}
    </div>
  )
}
