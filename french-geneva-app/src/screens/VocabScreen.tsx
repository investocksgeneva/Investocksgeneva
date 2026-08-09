import { useState } from 'react'
import type { VocabItem } from '../data/curriculum'
import { useProgress } from '../hooks/useProgress'
import { useSpeech } from '../hooks/useSpeech'

function Flashcard({ item }: { item: VocabItem }) {
  const [flipped, setFlipped] = useState(false)
  const { isVocabKnown, setVocabKnown } = useProgress()
  const { speak, supported } = useSpeech()
  const known = isVocabKnown(item.fr)

  return (
    <li className={`flashcard ${known ? 'known' : ''}`}>
      <button
        type="button"
        className="flashcard-face"
        onClick={() => setFlipped((f) => !f)}
      >
        <span className="flashcard-word">{flipped ? item.en : item.fr}</span>
        <span className="flashcard-hint">{flipped ? 'tap to see French' : 'tap to reveal'}</span>
      </button>
      <div className="flashcard-actions">
        {supported && (
          <button type="button" onClick={() => speak(item.fr)} aria-label={`Listen to ${item.fr}`}>
            🔊
          </button>
        )}
        <button
          type="button"
          className={`known-toggle ${known ? 'active' : ''}`}
          onClick={() => setVocabKnown(item.fr, !known)}
        >
          {known ? '✓ Known' : 'Mark known'}
        </button>
      </div>
    </li>
  )
}

export function VocabScreen({ vocab }: { vocab: VocabItem[] }) {
  const { knownVocabCount } = useProgress()

  return (
    <div className="screen">
      <div className="hero-card">
        <p className="hero-eyebrow">Vocabulary bank</p>
        <p className="hero-goal">
          ~{vocab.length} words for spaced repetition. Tap a card to flip it, listen for
          pronunciation, and mark words you've got down cold.
        </p>
        <div className="hero-progress">
          <div className="progress-bar">
            <div
              className="progress-bar-fill"
              style={{ width: `${(knownVocabCount / vocab.length) * 100}%` }}
            />
          </div>
          <span>
            {knownVocabCount}/{vocab.length} known
          </span>
        </div>
      </div>

      <ul className="flashcard-grid">
        {vocab.map((item) => (
          <Flashcard key={item.fr} item={item} />
        ))}
      </ul>
    </div>
  )
}
