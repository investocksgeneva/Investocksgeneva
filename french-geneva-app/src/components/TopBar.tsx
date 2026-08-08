export function TopBar({
  title,
  onBack,
}: {
  title: string
  onBack?: () => void
}) {
  return (
    <header className="top-bar">
      {onBack ? (
        <button type="button" className="back-btn" onClick={onBack} aria-label="Back">
          ←
        </button>
      ) : (
        <span className="top-bar-spacer" />
      )}
      <h1>{title}</h1>
      <span className="top-bar-spacer" />
    </header>
  )
}
