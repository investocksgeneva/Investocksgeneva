export type Tab = 'home' | 'vocab' | 'progress'

const items: { id: Tab; label: string; icon: string }[] = [
  { id: 'home', label: 'Lessons', icon: '📖' },
  { id: 'vocab', label: 'Vocabulary', icon: '🗂️' },
  { id: 'progress', label: 'Progress', icon: '📈' },
]

export function BottomNav({
  active,
  onChange,
}: {
  active: Tab
  onChange: (tab: Tab) => void
}) {
  return (
    <nav className="bottom-nav">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          className={`bottom-nav-item ${active === item.id ? 'active' : ''}`}
          onClick={() => onChange(item.id)}
        >
          <span className="bottom-nav-icon">{item.icon}</span>
          <span>{item.label}</span>
        </button>
      ))}
    </nav>
  )
}
