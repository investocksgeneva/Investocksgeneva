export function AskFab({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" className="ask-fab" onClick={onClick} aria-label="Ask a question">
      💬
    </button>
  )
}
